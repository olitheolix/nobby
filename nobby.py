#!/usr/bin/python3

# Copyright 2014, Oliver Nagy <olitheolix@gmail.com>
#
# This file is part of Nobby.
#
# Nobby is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# Nobby is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# Nobby. If not, see <http://www.gnu.org/licenses/>.

"""
Convert LaTeX code to HTML file plus SVG images.

Help:          run `nobby.py -h`
Unit tests:    run `py.test` in this directory.
Documentation: https://olitheolix.com/doc/nobby/
Source code:   https://github.com/olitheolix/nobby
"""

import re
import os
import sys
import time
import shutil
import config
import plugins
import IPython
import argparse
import webbrowser
import subprocess
import numpy as np
import collections
import multiprocessing
import matplotlib.pyplot as plt

ipshell = IPython.embed

# Meta information about delimiters in LaTeX code (eg. '$' or \begin).
Delim = collections.namedtuple('Delim', 'span isOpen type name')

# Convenience: contains all path- and file names that Nobby may need.
PathNames = collections.namedtuple(
    'PathNames', 'f_source f_tex f_html d_base d_build d_html')

# Record all macros and environments for which no plugin exists.
# Nobby will print the list in verbose (-v) mode.
no_plugins = []

# ----------------------------------------------------------------------------
#                               LaTeX Parsing
# ----------------------------------------------------------------------------


def findComments(body):
    """
    Return the span of all comments and a cleaned ``body``.

    The sanitised body returned by this function contains only white space
    where comments used to be.

    The comment delimiters are the '%' symbol and the newline character.

    .. inline-python::

        import pprint, nobby
        body = 'foo % bar\\n'
        body_sane, delim = nobby.findComments(body)
        print(body_sane)
        pprint.pprint(delim)

    :param *str* body: LaTeX file as string.
    :return: `[body_sane, delim]`
    :rtype: (**str**, **dict**)
    """
    body = body.replace(r'\%', '  ')
    delim = {}

    # Find all comments.
    pat = re.compile(r'%.*?\n')
    for m in pat.finditer(body):
        start, stop = m.span()
        delim[start] = Delim((start, start + 1), True, '%', None)
        delim[stop - 1] = Delim((stop - 1, stop), False, '%', None)

    # Neutralise all comments for the next parser.
    def repl(m):
        return ' ' * (len(m.group()) - 1) + '\n'
    body_sane = pat.sub(repl, body)
    return body_sane, delim


def findBeginEnd(body):
    """
    Return the span of all begin/end environments and a cleaned ``body``.

    The sanitised body returned by this function contains only white space
    where the environments used to be (this includes the \begin{} and \end{})
    parts themselves).

    The comment delimiters are '\begin{...}' and '\end{...}'

    .. inline-python::

        import pprint, nobby
        body = '\\\\begin{foo}bar\\\\end{foo}'
        body_sane, delim = nobby.findBeginEnd(body)
        print(body_sane)
        pprint.pprint(delim)

    :param *str* body: LaTeX file as string.
    :return: `[body_sane, delim]`
    :rtype: (**str**, **dict**)
    """
    delim = {}

    def repl(m):
        return ' ' * len(m.group())

    # Find all \begin{env-name}, extract 'env-name', and create a new **Delim**
    # instance for it.
    pat = re.compile(r'\\begin{(.*?)}')
    for m in pat.finditer(body):
        start, stop = m.span()
        env_name = m.groups()[0]
        delim[start] = Delim((start, stop), True, 'env', env_name)
    body_sane = pat.sub(repl, body)

    # Repeat for \end{env-name}.
    pat = re.compile(r'\\end{(.*?)}')
    for m in pat.finditer(body_sane):
        start, stop = m.span()
        env_name = m.groups()[0]
        delim[start] = Delim((start, stop), False, 'env', env_name)
    body_sane = pat.sub(repl, body_sane)
    return body_sane, delim


def findCurly(body):
    """
    Return the span of all braced environments.

    This function blanks all escaped curly braces and then searches for
    all other curly braces.

    The comment delimiters are '{' and '}'.

    .. inline-python::

        import pprint, nobby
        body = 'foo {inside} bar\\n'
        body_sane, delim = nobby.findCurly(body)
        print(body_sane)
        pprint.pprint(delim)

    :param *str* body: LaTeX file as string.
    :return: `[body_sane, delim]`
    :rtype: (**str**, **dict**)
    """
    body_sane = body.replace(r'\{', '  ')
    body_sane = body_sane.replace(r'\}', '  ')
    delim = {}

    # Find all opening brackets.
    for _ in re.finditer(r'{', body_sane):
        start, stop = _.span()
        delim[start] = Delim((start, stop), True, '{', None)

    # Find all closing brackets.
    for _ in re.finditer(r'}', body_sane):
        start, stop = _.span()
        delim[start] = Delim((start, stop), False, '}', None)
    return body_sane, delim


def findDollar(body):
    """
    Return the span of all comments and a cleaned``body``.

    This function blanks the span of all $ and $$ environments.

    The comment delimiter is either '$' or '$$' both ends.

    .. inline-python::

        import pprint, nobby
        body = 'a $b$ c $$d$$ e \$f\\n'
        body_sane, delim = nobby.findDollar(body)
        print(body_sane)
        pprint.pprint(delim)

    :param *str* body: LaTeX file as string.
    :return: `[body_sane, delim]`
    :rtype: (**str**, **dict**)
    """
    # Replace all escaped $-symbols with white space.
    body = body.replace(r'\$', '  ')

    # Find all $ and $$ environments.
    delim = {}
    pat = re.compile(r'(\${1,2})(.*?)(\${1,2})', flags=re.DOTALL)
    for m in pat.finditer(body):
        start, stop = m.span()

        # Sanity check to ensure that the number of '$' signs found at the
        # beginning match that at the end.
        assert m.groups()[0] == m.groups()[2]

        # The delimiter character ('$' or '$$') and its length.
        delim_char = m.groups()[0]
        l = len(delim_char)

        # Construct two **Delim** instances.
        delim[start] = Delim((start, start + l), True, delim_char, None)
        delim[stop-l] = Delim((stop - l, stop), False, delim_char, None)

    # Replace all $ and $$ environments with white space.
    def repl(m):
        return ' ' * len(m.group())
    body_sane = pat.sub(repl, body)
    return body_sane, delim


def findNewline(body):
    """
    Return the span of all newline '\\' symbols.

    There is only one delimiter, namely the '\\' symbol. Technically, this
    defines a macro, but due to the nature of the backslash it is easier to
    handle it explicitly instead of implicitly via :func:`findMacros`.

    .. inline-python::

        import pprint, nobby
        body = 'foo \\\\\\\\ bar\\n'
        body_sane, delim = nobby.findNewline(body)
        print(body_sane)
        pprint.pprint(delim)

    :param *str* body: LaTeX file as string.
    :return: `[body_sane, delim]`
    :rtype: (**str**, **dict**)
    """
    delim = {}

    # Find all double-backslash symbols.
    pat = re.compile(r'\\\\')
    for m in pat.finditer(body):
        start, stop = m.span()
        delim[start] = Delim((start, stop), None, 'macro', '\\')

    # Replace all newline commands with white space.
    body_sane = pat.sub('  ', body)
    return body_sane, delim


def findMacros(body):
    """
    Return the span of all macros and a cleaned ``body``.

    The comment delimiters are everything from the backslash to the first
    non-alphabetical character.

    .. inline-python::

        import pprint, nobby
        body = '\\ldots \ldots8 \ldots{\\n'
        body_sane, delim = nobby.findMacros(body)
        print(body_sane)
        pprint.pprint(delim)

    :param *str* body: LaTeX file as string.
    :return: `[body_sane, delim]`
    :rtype: (**str**, **dict**)
    """
    delim = {}

    # Find all macros, ie search for '\macroname' and extract 'macroname'.
    pat = re.compile(r'(\\.*?)(?![a-zA-Z*])')

    # The parser below uses a while loop instead of `re.finditer` because I do
    # not know how to construct a regular expression that matches up to, but
    # not including, any alphabetical characters.
    stop = 0
    m = pat.search(body, stop)
    while m is not None:
        # The span starts where the RE says, but may end earlier, depending on
        # the character that follows. For this reason, determine the macro name
        # and use its length to determine the end of the span.
        start = m.span()[0]
        name = m.groups()[0]
        stop = start + len(name)

        # Remove the leading backslash.
        name = name[1:]

        # If the first character was one of LaTeX' special characters then the
        # RE would have returned the backslash symbol only, since none of the
        # special characters matches [a-zA-Z] of the RE. In this case, do not
        # construct a macro delimiter but move on. The previous statement
        # removed the backslash already, which means name would be an empty
        # string if we had encountered any escaped special character sequences
        # like \$, \^, \_ etc.
        if len(name) == 0:
            m = pat.search(body, stop)
            continue

        # Construct the **Delim** tuple and continue the search.
        delim[start] = Delim((start, stop), None, 'macro', name)
        m = pat.search(body, stop)
    return body, delim


def pruneDelimiters(delim_list, plugins=None):
    """
    Return pruned delimiter list.

    The input to this function is usually the output of
    :func:`findDelimiters`. That function may return an inconsistent set of
    delimiters because LaTeX environments are at liberty to redefine the
    meaning of eg '\\' inside an array environment.

    This function compounds this problem and removes all delimiters nested
    inside other environments, save those for which plugins exists. If no such
    ``plugins`` exists, then all delimiters inside any '$', '$$', \begin-\end
    block drop out of the list, leaving only text and said top level
    environments. Conversely, the pruning ignores delimiters for which plugins
    exist.

    .. inline-python::

        import pprint, nobby

        # Find all delimiters. These include the ones for the 'bar'
        # environment, as well as for the nested '$', and the text inside that
        # '$' environment.
        body = r'foo \\begin{bar} $x$ \\end{bar}'
        out = nobby.findDelimiters(body)
        pprint.pprint(out)

        # Remove delimiters inside other environments. This removes everything
        # inside the 'bar' environment, including the '$' environment and its
        # text inside.
        out_prune = nobby.pruneDelimiters(out)
        pprint.pprint(out_prune)

        # Same example, but this time tell pruneDelimiters that there is
        # a plugin for the 'bar' environment available. As a consequence,
        # the '$' delimiters prevails, but still not the text inside that '$'
        # environment.
        out_prune = nobby.pruneDelimiters(out, plugins=['bar'])
        pprint.pprint(out_prune)

    :param *list* delim_list: list of **Delim** objects/tuples.
    :param *dict* plugins: dictionary of plugins.
    :return: pruned list of **Delim** objects/tuples.
    :rtype: **list**
    """
    # Create an empty list if no plugins were supplied.
    if plugins is None:
        plugins = {}

    # Remove everything in between $ and $$. This is unnecessary if the input
    # comes directly from findDelimiters, but is a useful safety measure
    # regardless.
    delim_pruned = []
    keep = True
    for item in delim_list:
        if item.type in ('$', '$$'):
            # Entering a new '$' or '$$' environment: keep the delimiter but
            # toggle ``keep`` and reject all further delimiters until the
            # environment is closed again.
            delim_pruned.append(item)
            keep = not keep
        elif keep:
            # Not a '$' or '$$' environment, but add it anyway because ``keep``
            # is set, which means we are not inside a '$' environment.
            delim_pruned.append(item)
        else:
            pass

    # The pruned delimiter list is the new input for the second
    # stage. This stage prunes the delimiters inside environments.
    delim_list = delim_pruned
    del delim_pruned, keep

    # Remove all delimiters inside any environment for which we have no plugin.
    delim_pruned = []
    idx = 0
    while idx < len(delim_list):
        # Convenience.
        item = delim_list[idx]

        # Keep the delimiter in any case. If it does denote an environment then
        # move to the next delimiter.
        delim_pruned.append(item)
        if item.type != 'env':
            idx += 1
            continue

        # Ignore the delimiter if denotes an environment for which we have a
        # plugin, and move on to the next delimiter.
        if item.name in plugins:
            idx += 1
            continue

        # At this point we are dealing with an environment for which we have no
        # plugin. Continue to traverse the delimiter list until the closing
        # delimiter is found. In pursuit of the closing delimiter, take heed of
        # nested environments with the same name.
        open_name = item.name
        depth = 1

        # Sanity check
        assert item.isOpen

        # Traverse the list until the matching closing delimiter is found.
        while True:
            # Progress to next item and extract it for convenience.
            idx += 1
            item = delim_list[idx]

            # Skip if it is not an 'env' with the desired name.
            if not ((item.type == 'env') and (item.name == open_name)):
                continue

            # We are now dealing with an 'env' that has the correct name. If
            # its `isOpen` flag is true, then we have another env nested inside
            # the original one. In that case, increase the nesting depth
            # counter, otherwise, decrease it because an 'env' with the correct
            # name was closed.
            if item.isOpen:
                depth += 1
            else:
                depth -= 1

            # We found the matching end of the 'env' if the nesting depth
            # reaches zero. In that case, add the closing delimiter to the list
            # and proceed with the outer loop.
            if depth == 0:
                delim_pruned.append(item)
                idx += 1
                break
    return delim_pruned


def findDelimiters(body):
    """
    Return list of all **Delim** instances.

    The delimiters comprise '$', \begin and \end, etc.

    The returned list accounts for every byte in the LaTeX ``body``. Its
    constituents specify the position and length of every delimiter.

    Delimiters have different lengths. For instance, '$' and '$$' environments
    have one- and two byte long delimiters, whereas '\begin{itemize}' is 15
    characters long, and plain text delimiters are zero bytes long.

    The output of this function almost certainly requires some pruning to
    ensure consistency. :func:`pruneDelimiters` will do that.

    :param *str* body: LaTeX code as string.
    :return: pruned list of **Delim** objects/tuples.
    :rtype: **list**
    """
    # Return immediately if body is empty.
    if body == '':
        return {}

    delim = {}

    # ------------------------------------------------------------------------
    # Run all the delimiter parser. Their order matters because the substitute
    # all their matches with blank space. For instance, \begin looks like any
    # other macro (eg. \ldots), which is why ``findBeginEnd`` must run before
    # ``findMacro``. If not, the latter would blank out every \begin and \end.
    # ------------------------------------------------------------------------
    body_sane, tmp = findComments(body)
    delim.update(tmp)

    body_sane, tmp = findBeginEnd(body_sane)
    delim.update(tmp)

    body_sane, tmp = findCurly(body_sane)
    delim.update(tmp)

    body_sane, tmp = findDollar(body_sane)
    delim.update(tmp)

    body_sane, tmp = findNewline(body_sane)
    delim.update(tmp)

    body_sane, tmp = findMacros(body_sane)
    delim.update(tmp)

    # Sanity check: all spans must increase monotonically.
    keys = list(delim.keys())
    keys.sort()
    for idx in range(len(keys) - 1):
        d0 = delim[keys[idx]]
        d1 = delim[keys[idx + 1]]
        assert d0.span[1] <= d1.span[0]

    # ------------------------------------------------------------------------
    # Add text delimiters. These span from the stop of the previous delimiter
    # to the start of the next.
    # ------------------------------------------------------------------------
    out = []
    start = 0
    for key in sorted(delim):
        # Find the span from the end of the last delimiter to the start of the
        # current one.
        d = delim[key]
        stop = d.span[0]

        # Sanity check.
        assert start <= stop

        # If start < stop, but not start == stop, then the span has non-zero
        # length and thus requires a start/stop delimiter for the text in
        # between.
        if start < stop:
            out.append(Delim((start, start), True, 'text', None))
            out.append(Delim((stop, stop), False, 'text', None))

        # Add the original delimiter and set the new start position to the end
        # of the current delimiter.
        out.append(d)
        start = d.span[1]
        del d, stop

    # Manually insert the text beyond the last delimiter.
    if start < len(body):
        stop = len(body)
        d0 = Delim((start, start), True, 'text', None)
        d1 = Delim((stop, stop), False, 'text', None)
        out.extend([d0, d1])
        del stop, d0, d1

    # The very first span may be zero due to the algorithm above. Remove it.
    if out[1].span == (0, 0):
        out = out[2:]

    # Sanity check.
    for idx in range(len(out) - 1):
        s0 = out[idx].span
        s1 = out[idx + 1].span
        assert s0[0] <= s0[1] <= s1[0] <= s1[1]

    # Return the information as a list of **Delim** tuples, sorted by the start
    # position of the delimiters.
    return out


# ----------------------------------------------------------------------------
#  Convert LaTeX document to tree. Convert tree to HTML, create fragment list,
#  and call the plugins.
#  ----------------------------------------------------------------------------

class TreeNode():
    """
    A node in the tree representation of a LaTeX document.

    Every node features a body and a list of children. The body is a piece of
    LaTeX code (a string), and the concatenation of all children via
    reconstructBody reproduces that string.

    There are several node types, most notably 'text', 'env', 'macro' and
    'comment'.

    Every node also has a span to identify the text portion in the original
    LaTeX document. This field is as yet unused.
    """
    def __init__(self, parent, ntype, span, name):
        self.parent = parent

        # One of 'text', 'env', 'macro', 'comment' and few more.
        self.type = ntype

        # The span in the original LaTeX document.
        assert isinstance(span, (tuple, list)) and (len(span) == 2)
        self.span = span

        # Find the set of LaTeX counters closes to the span of this node.
        counters = config.counter_values
        for idx, cc in enumerate(counters):
            if self.span[0] == cc.start:
                self.counters = cc.counters
                break
            elif self.span[0] < cc.start:
                if idx == 0:
                    self.counters = counters[0].counters
                else:
                    self.counters = counters[idx - 1].counters
                break
            else:
                pass

        # Contains the LaTeX code *without* the delimiter strings (eg. '{')
        self.body = None

        # List of child nodes.
        self.kids = []

        # Macro- or environment name (eg 'ldots' or 'itemize'), or a short
        # string to denote the environment (eg. 'text' or 'curly1' for a curly
        # brace environment). Either way, this field will server as the image
        # name should the become a fragment compiled with pdfLaTeX (likely to
        # be the case for all but 'text' nodes).
        self.name = name
        if self.type in ('macro', 'env'):
            assert self.name is not None

        # Fill in the name field for non macro/env nodes, and also populate the
        # LaTeX delimiters for the node type (eg. '{' '$', '$$', etc).
        self.updateNode()

    def reconstructBody(self, node=None):
        """
        Reconstruct and return the LaTeX code fragment including delimiters.

        If the ``node`` argument is not provided then the body is built from
        the current node.

        :param *TreeNode* node: optional node (points to *self* by default).
        :return *str*: node body plus LaTeX delimiters.
        """
        # Assemble the current node unless specified otherwise.
        if node is None:
            node = self

        # Return the node body with the delimiters attached.
        return node.pre + node.body + node.post

    def verifyNode(self):
        """
        Check if the body of this node equals the concatenation of all child
        node bodies.

        ..note: Nodes without children are always consistent.

        :return **bool**: *True* if the node is consistent.
        """
        # Nodes without children are always consistent.
        if len(self.kids) == 0:
            return True

        # Concatenate the children. To do so, run reconstructBody on each of
        # them to attach the correct delimiters and concatenate the returned
        # strings.
        out = ''
        for c in self.kids:
            out += self.reconstructBody(c)

        if out != self.body:
            # The strings do not match. This is almost certainly a bug. Write a
            # debug file with the content node body and reconstructed string.
            print('Node is inconsistent - see <delme_body.txt> and '
                  '<delme_nodes.txt> for details')
            open('delme_body.txt', 'w').write(self.body)
            open('delme_nodes.txt', 'w').write(out)
            return False
        else:
            # All good.
            return True

    def updateNode(self):
        """
        Populate the pre-, post-, and name attributes of the :func:`TreeNode`.

        Some sanity checks are applied along the way.

        :return: **None**
        """
        if self.type == 'text':
            self.pre = self.post = ''
            self.name = 'text_'
        elif self.type == 'html':
            self.pre = self.post = ''
            self.name = 'html_'
        elif self.type == '$':
            self.pre = self.post = '$'
            self.name = 'dollar1_'
        elif self.type == '$$':
            self.pre = self.post = '$$'
            self.name = 'dollar2_'
        elif self.type == '{':
            self.pre, self.post = '{', '}'
            self.name = 'curly1_'
        elif self.type == '{{':
            self.pre, self.post = '{{', '}}'
            self.name = 'curly2_'
        elif self.type == '%':
            # The comment delimiters are '%' and '\n'.
            self.pre, self.post = '%', '\n'
            self.name = 'comment_'
        elif self.type == 'env':
            # Constructor must have set the env name.
            assert self.name is not None
            self.pre = r'\begin{' + self.name + '}'
            self.post = r'\end{' + self.name + '}'
        elif self.type == 'macro':
            # Constructor must have set a macro name. Macro delimiters are a
            # backslash at the start, and nothing at the end.
            assert self.name is not None
            self.pre, self.post = '\\' + self.name, ''
        else:
            print('Bug. Unknown node type <{}>'.format(self.type))


def verifyTree(node):
    """
    Verify that the node are consistent.

    Nodes are consistent if the ``verifyNode`` returns *True*. It will do so if
    the child nodes can reconstruct node.body (see :func:`verifyNode` for
    details).

    This function is a sanity check. The program aborts if it fails. If it
    does, then there is most likely a bug.

    :param *TreeNode* node:
    :return: **None**
    """
    # Return immediately if we are in a leaf.
    if len(node.kids) == 0:
        return

    # Verify node consistency.
    if not node.verifyNode():
        print('Tree is inconsistent - abort')
        sys.exit(1)

    # Move to the next kid.
    for ch in node.kids:
        verifyTree(ch)


def buildTree(body, delim_list):
    """
    Build the tree for the LaTeX ``body`` based on the ``delim_list``.

    The ``delim_list`` determines the span of every node.

    The tree structure does not represent the sectioning of the LaTeX document,
    ie it is not a DOM. Instead it partitions the document into blocks, each
    represented by a single node. The blocks can be eg. text, an equation ('$'
    or '$$' delimiters), macros (eg. ldots), or environments (eg. itemize). The
    block/node may have other blocks inside it, eg. a '$' environment inside an
    'itemize' block.

    For instance, if the LaTeX code is 'foo \begin{itemize} bar $x$
    \end{itemize} \ldots', then the root node is:

    root.body = 'foo \begin{itemize} bar $x$ \end{itemize} \ldots'
    root.kids[0].body = 'foo '            # 'text' (node.name = 'text')
    root.kids[1].body = 'bar $x$'         # 'env' (node.name = 'itemize')

      root.kids[1].kids[0].body = 'bar '  # text (node.name = 'text')
      root.kids[1].kids[1].body = 'x'     # eqn (node.name = 'dollar1')

    root.kids[2].body = ' '               # text (node.name = 'text')
    root.kids[3].body = 'ldots'           # macro (node.name = 'ldots')

    Note that the bodies never contain the delimiters itself, eg. root.kids[1]
    lacks 'begin{itemize}', as does root.kids[1].kids[1].body lack the '$'
    delimiter. The :func:`reconstructBody` method of every node takes care to
    re-attach the correct delimiters to reconstruct the body of the parent.

    :param *str* body: LaTeX code.
    :param *list* delim_list: list of **Delim** instances.
    :rtype: **TreeNode**
    :return: Root node.
    """
    # Create the root node of the tree. It contains the entire document, has
    # not type- and parent, and spans the entire document.
    root = TreeNode(None, 'text', (0, len(body)), None)
    root.body = body

    # Pointer to current node. The logic below will update it as the tree
    # unfolds.
    cur_node = root

    # Traverse the delimiter list and build the tree. Create a new node and
    # descend into it at every opening delimiter. Ascend at every closing
    # delimiter.
    for delim in delim_list:
        if delim.isOpen is True:
            # Found an opening delimiter.
            #
            # Create a new node, populate it with the available information,
            # and install it as another child.
            new_node = TreeNode(cur_node, delim.type, delim.span, delim.name)
            cur_node.kids.append(new_node)

            # Descend into the node.
            cur_node = new_node
            del new_node
        elif delim.isOpen is False:
            # Found a closing delimiter.
            #
            # 'cur_node' holds the start/stop position of the delimiter. To
            # extract the body, we start after the delimiter, and continue to
            # the start of the next delimiter.
            b_start = cur_node.span[1]
            b_stop = delim.span[0]
            assert b_start <= b_stop

            # The node spans from after the start-delimiter to before the
            # stop-delimiter.
            cur_node.span = cur_node.span[0], delim.span[1]
            cur_node.body = body[b_start:b_stop]

            # Set the delimiters.
            cur_node.updateNode()
            cur_node = cur_node.parent
            del b_start, b_stop
        elif (delim.isOpen is None) and (delim.type == 'macro'):
            # Neither opening nor closing delimiter, but a macro.  Macros do
            # not have start/stop delimiters like eg. equations ('$' or '$$'),
            # or environments (\begin{} end{}). Instead they are just a
            # alphabetical string preceded by a backslash and terminated with
            # any non-alphabetical character (eg. white space, a number, brace,
            # etc).  Macro may have arguments, but they play no role in the
            # tree construction. The :func:`convertTreeToHTML` function will
            # take care of it.

            # Create the macro node. It has no body, only a name.
            new_node = TreeNode(cur_node, delim.type, delim.span, delim.name)
            new_node.body = ''

            # Install the node as a new kid.
            cur_node.kids.append(new_node)
            del new_node
        else:
            # This should not happen.
            print('Bug')
            sys.exit(1)

    # Sanity check: ensure the fragments are consistent. The :func:`verifyTree`
    # function will abort the program if not.
    verifyTree(root)
    return root


def convertTextToHTML(body):
    """
    Return HTML version of ``body`` without accidental HTML tags.

    This function does little more than replacing escaped LaTeX character
    (eg. '\%', '\$', '\{') with their HTML string equivalent.

    In addition, this function will also escape an '<>' symbols to avoid
    accidental HTML tags.

    The assumption is that ``body`` does not contain any macro tags, including
    the '\\' macro.

    .. inline-python::

        import nobby

        body = r'a \$ b \{ c \} d \%'
        out = nobby.convertTextToHTML(body)
        print(out)

    :param *str* body: text fragment to convert.
    :return: escaped and sanitised version HTML of ``body``.
    :rtype: **str**
    """
    # Replace escaped LaTeX characters.
    special = ['#', '$', '%', '&', '\\', '^', '_', '{', '}', '~']
    for ch in special:
        body = body.replace('\\{}'.format(ch), ch)

    # Replace HTML tag delimiters.
    body = body.replace('<', '&lt;')
    body = body.replace('>', '&gt;')

    # Replace quotes.
    body = body.replace("``", '&ldquo;')
    body = body.replace("''", '&rdquo;')

    return body


def convertTreeToHTML(node, frag_list, plugins):
    """
    Convert a LaTeX tree into a HTML file and return the fragments.

    This function converts the children of ``node`` into HTML code. A new
    fragment is added to ``frag_list`` if the child is anything but text.
    The only exception from this rule are macros and environments for
    which a ``plugin`` exists. Plugins will do the conversion in that case
    (see :func:`runPlugin` for details).

    The elements in ``frag_list`` will later be compiled into SVG images.

    The ``plugins`` dictionary should be the same as the one passed to
    :func:`pruneDelimiters`.

    :param *TreeNode* node: starting node of tree (usually the root node)
    :param *list* frag_list: a list-like object to add every new
      fragments. This parameter is usually an empty list and serves as a return
      value for the caller.
    :param *dict* plugins: dictionary of plugin functions that convert
      various macros and environments.
    :param *str* html: initial HTML code.
    :return: HTML code for ``node``.
    :rtype: **str**
    """
    # Return immediately if the node has no children.
    if len(node.kids) == 0:
        return ''
    else:
        html = ''

    # Traverse all child nodes. Do not use a for-loop because the number of
    # elements in this list may change during the loop, depending on how many
    # nodes the plugins return. The loop itself inspects the nodes and
    # (roughly) does the following:
    #   * nothing, if it is a text node (just append the HTML text),
    #   * call a plugin, insert the nodes it returns, and continue with them
    #   * create a fragment in all other cases.
    child_idx = 0
    while child_idx < len(node.kids):
        # Convenience.
        child = node.kids[child_idx]

        if child.type == 'macro':
            # Make all braced environments that follow the macro children of
            # that macro node. The entire node will then be passed to the
            # respective macro plugin (if one exists). The plugin is
            # responsible for interpreting the arguments and to return all
            # unnecessary ones back.
            #
            # From: (other) - (macro) - (brace) - (brace) - (other)
            #
            # To: (other) - (macro) - (other)
            #                  |
            #         ---------------------
            #         |        |          |
            #      (brace) - (brace) - (brace)
            try:
                while node.kids[child_idx+1].type in ['{', 'text']:
                    tmp = node.kids[child_idx+1]
                    # A 'text' node is also a brace note if it starts and ends
                    # with '[' and ']', respectively (optional argument in
                    # LaTeX lingo).
                    if tmp.type == 'text':
                        if (tmp.body[0], tmp.body[-1]) != ('[', ']'):
                            break
                    child.kids.append(node.kids.pop(child_idx+1))
            except IndexError:
                pass

            # Update the body of the macro node from the empty string (as for
            # all macro nodes) to the concatenation of all the children it just
            # gained.
            child.body = ''
            for kid in child.kids:
                kid.parent = child
                child.body += child.reconstructBody(kid)
            child.verifyNode()

        if child.type == 'html':
            html += child.body
            child_idx += 1
        elif child.type == 'text':
            # Text node: add the node body to the HTML text and move
            # on. Convert empty lines into paragraphs first.
            tmp = convertTextToHTML(child.body)
            html += re.sub(r'\n *?\n', '<p>', tmp, re.MULTILINE)
            child_idx += 1
            del tmp
        elif child.type == '{':
            # Braced environment: first, check if it is actually a double
            # braced environment (ie. the node has exactly one child which is
            # itself a '{' environment).
            if (len(child.kids) == 1) and (child.kids[0].type == '{'):
                # It is indeed a single brace environment inside another single
                # brace environment, which means the two nodes can be merged
                # into a single double brace environment.
                child.type = '{{'
                tmp = TreeNode(node, '{{', child.span, None)
                tmp.body = child.kids[0].body

                # Double brace environments become fragments by definition.
                html += createFragmentDescriptor(tmp, frag_list)
                del tmp
            else:
                # A single curly brace environment: descend.
                html += convertTreeToHTML(child, frag_list, plugins)

            # Continue with next child, regardless of whether it was a single-
            # or double braced environment.
            child_idx += 1
        elif (child.type == 'macro') and (child.name == '\\'):
            # Replace any LaTeX newline command (ie. '\\') with a text node
            # that contains the r'\\' string. This cannot be done earlier,
            # because everything starting with a backslash would otherwise have
            # been identified as a macro.
            old = node.kids.pop(child_idx)
            new_node = TreeNode(node, 'text', old.span, old.name)
            new_node.body = '\\\\'
            node.kids.insert(child_idx, new_node)
            html += '<p>'
            child_idx += 1
            del old, new_node
        elif child.name in plugins:
            # Pick the plugin.
            func = plugins[child.name]

            # Execute the plugin via the ``runPlugin`` wrapper (it ensures sane
            # input and output). All kids are macro/env arguments.
            ret_nodes = runPlugin(func, child)

            # Replace the original node with those returned by the plugin.
            node.kids.pop(child_idx)
            for _ in reversed(ret_nodes):
                node.kids.insert(child_idx, _)
            del func, ret_nodes
        else:
            # Convert the fragment to an SVG image.

            # Find all labels inside the fragment and add the corresponding
            # HTML anchor tag. It is necessary to count the number of labels,
            # because if there are multiple of them, then multiple anchors will
            # be created, which all require a closing </a> tag in the HTML
            # output.
            p = re.compile(r'\\label({.*?})')
            num_labels = 0
            for m in p.finditer(child.body):
                labelname = m.groups()[0]
                labelname = labelname[1:-1]
                html += '<a name="{}">'.format(labelname)
                num_labels += 1
                del labelname, m
            del p

            # Create a new fragment descriptor based on the node body. The
            # function will return the necessary HTML code to load the image.
            html += createFragmentDescriptor(child, frag_list)

            # Close the anchor tags.
            html += '</a>' * num_labels

            # Keep a list of all converted nodes, unless they are too benign
            # to mention.
            if child.name not in config.benign_node_types:
                no_plugins.append((child.type, child.name))

            # Move on to the next child.
            del num_labels
            child_idx += 1

    return html


def runPlugin(func, node):
    """
    Wrapper for `func(kids)`. Return sanitised output of that function.

    The plugin ``func`` (should) return a list and this function ensures it
    really does. The list must contain only :func:`TreeNode` object, or
    strings. Strings will be automatically converted to :func:`TreeNode`
    objects (ie. text nodes).

    :param *callable* func: the plugin function.
    :param *TreeNode* node: current node that requires the plugin
    :return: list of :func:`TreeNode` objects.
    :rtype: list of **TreeNodes**
    """
    # Call the plugin and ensure the return value is a tuple.
    ret_nodes = func(node.kids, node)
    if not isinstance(ret_nodes, (tuple, list)):
        ret_nodes = (ret_nodes, )

    # Sort the return values into a single list. However the plugin may return
    # a list that contains both strings, as well as other lists of nodes. The
    # following code flattens the structure so that sane_nodes will not contain
    # any lists itself. For instance, if the plugin returns (str, (node1,
    # node2), str) then sane_nodes = (str, node1, node2, str).
    sane_nodes = []
    for nn in ret_nodes:
        if isinstance(nn, (list, tuple)):
            sane_nodes.extend(nn)
        else:
            sane_nodes.append(nn)
        del nn

    # Convert every string to a proper text node. Ensure that all other list
    # entries are :func:`TreeNode` instances.
    out = []
    for nn in sane_nodes:
        if isinstance(nn, str):
            # Do not bother to create a text node for an empty string.
            if nn == '':
                continue

            # Create a text node.
            ret_nodes = TreeNode(node.parent, 'html', node.parent.span, None)
            ret_nodes.body = nn
            out.append(ret_nodes)
        elif isinstance(nn, TreeNode):
            # nn is already a TreeNode instance.
            out.append(nn)
        else:
            msg = 'The <{}> plugin returned the unexpected type <{}> - Abort.'
            print(msg.format(func.__name__, type(nn)))
            sys.exit(1)
    # Return the sanitised list of TreeNode objects.
    return out


def createFragmentDescriptor(child, frag_list):
    """
    Add fragment for ``child`` to ``frag_list`` and return HTML <img> tag.

    The ``frag_list`` elements are self contained LaTeX code fragments that can
    be compiled individually to SVG images with the two external programs
    `pdflatex` and `pdf2svg`.

    :param *str* fname_tex: name of LaTeX file (eg. 'my_file.tex').
    :param *str* build_dir: pdfLaTeX will put its output there.
    :return *str*: HTML image tag.
    """
    # Initialise the fragment data structure.
    cur_frag = {'name': child.type}

    # Create the fragment name as per the placeholder format specified in the
    # configuration file. This name will also serve as the file name of the SVG
    # file, which means it should only contain characters that are safe to use
    # in file names. To compound ambiguous file names, every file name also
    # contains the length of the fragment list. This list can only grow, and
    # its length therefore provides a unique ID.
    ph = config.ph_format.format(child.name, len(frag_list))
    cur_frag['placeholder'] = ph

    # Create the HTML image tag, ie. something like <img=src="...">
    tag = config.tag_format
    tag = tag.format(ph)

    # In the HTML code, place the image in a new paragraph if its source code
    # constitutes an environment (ie. anythin between a '\begin' '\end' block
    # in LaTeX). Do not add a paragraph anywhere else to facilitate inline
    # equations in the HTML output.
    if child.type == 'env':
        tag = '<div align="center">' + tag + '</div>'
        cur_frag['inline'] = False
    else:
        cur_frag['inline'] = True

    # Add the LaTeX code fragment to finalise the fragment, then add it to the
    # already existing ``frag_list``.
    cur_frag['tex'] = child.reconstructBody()
    cur_frag['span'] = child.span

    # Convenience.
    counters = config.counter_values

    # Find the correct counter set.
    cur_frag['counters'] = None
    for idx, cc in enumerate(counters):
        if child.span[0] == cc.start:
            cur_frag['counters'] = counters[idx].counters
            break
        elif child.span[0] < cc.start:
            if idx == 0:
                cur_frag['counters'] = counters[0].counters
            else:
                cur_frag['counters'] = counters[idx - 1].counters
            break
        else:
            pass

    if (cur_frag['counters'] is None):
        if len(counters) == 0:
            cur_frag['counters'] = {}
        else:
            cur_frag['counters'] = counters[-1].counters

    frag_list.append(cur_frag)
    return tag


# ----------------------------------------------------------------------------
#                            PDF and SVG Creation
# ----------------------------------------------------------------------------


def runPDFLaTeX(build_dir: str, fname_tex: str):
    """
    Compile the file ``fname_tex`` with pdfLaTeX.

    The ``build_dir`` will contain all the intermediate files created by
    pdfLaTeX, including the final PDF file. This avoids clutter in the main
    directory.

    This function changes to the directory with the LaTeX file to avoid
    problems with relative file paths inside the LaTeX document. Afterwards, it
    will change back to the original working directory.

    :param *str* fname_tex: name of LaTeX file (eg. 'my_file.tex').
    :param *str* build_dir: pdfLaTeX will put its output there.
    :return: **namedtuple** with all auxiliary output files produced by LaTeX,
      including 'aux', 'out', and 'log'.
    """
    # Return immediately if the source file cannot be read.
    if not os.path.exists(fname_tex):
        print('Cannot open file <{}>'.format(fname_tex))
        return None, None

    # Create the build directory if it does not exist (pdflatex does not create
    # it automatically).
    try:
        os.mkdir(build_dir)
    except FileExistsError:
        pass

    # Get absolute path to build directory.
    build_dir = os.path.abspath(build_dir)

    # Backup current working directory.
    cur_path = os.getcwd()

    # Switch to the directory with the LaTeX file to ensure pdflatex has the
    # correct relative paths specified in the document (eg. \includegraphics
    # directives).
    compile_path, compile_file = os.path.split(fname_tex)
    if compile_path == '':
        compile_path = './'
    os.chdir(compile_path)

    if config.verbose:
        print('Compiling <{}>'.format(fname_tex))
    try:
        if config.use_latexmk:
            # Compile the LaTeX file.
            args = ('latexmk', '-quiet', '-output-directory=' + build_dir,
                    '-pdf', ('-pdflatex=pdflatex -halt-on-error '
                             '-interaction=nonstopmode'), compile_file)
            num_compile_iter = 1
        else:
            # Compile the LaTeX file.
            args = ('pdflatex', '-halt-on-error', '-interaction=nonstopmode',
                    '-output-directory=' + build_dir, compile_file)
            num_compile_iter = config.num_compile_iter

        for ii in range(config.num_compile_iter):
            subprocess.check_call(args, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
    except Exception as e:
        # Switch back to the original directory and propagate the error.
        os.chdir(cur_path)
        raise e

    # ----------------------------------------------------------------------
    # Load all auxiliary output files produced by LaTeX and put their
    # content into a named tuple.
    # ----------------------------------------------------------------------
    # Load the source file.
    aux_files = {'tex': open(compile_file, 'r').read()}

    # These files must exist.
    try:
        for name in ['log', 'aux', 'out']:
            # Build the file name and load it, if it exists.
            fname = os.path.join(build_dir, compile_file[:-3] + name)
            aux_files[name] = open(fname, 'r').read()
    except FileNotFoundError as e:
        print('Error: could not open all auxiliary files')
        raise e

    # The .nobby file only exists if Nobby salted the LaTeX file with
    # counter dumps.
    try:
        fname = os.path.join(build_dir, compile_file[:-3] + 'nobby')
        aux_files['nobby'] = open(fname, 'r').read()
    except FileNotFoundError:
        aux_files['nobby'] = None

    # Convert the dictionary to a named tuple and return the result.
    TexOut = collections.namedtuple('TexOut', 'tex log aux out nobby')
    val = [aux_files[_] for _ in TexOut._fields]
    tex_out = TexOut(*val)

    # Switch back to the original directory, then return the auxiliary files.
    os.chdir(cur_path)
    return tex_out


def getCropBox(fname):
    """
    Return the crop box size of the ``fname`` PDF as returned by `pdfinfo`.

    Example:

    .. inline-python::

        import pprint, nobby
        crop_box = nobby.getCropBox('source/code_snippets/demo.pdf')
        pprint.pprint(crop_box)

    :param **str** fname: name of PDF.
    :return: `[left, top, right and bottom]`
    :rtype: [**float**, **float**, **float**, **float**]
    """
    # Run pdfinfo on ``fname``.
    try:
        out = subprocess.check_output(('pdfinfo', '-box', fname))
    except subprocess.CalledProcessError as e:
        # Process returned with non-zero exit code: dump its output.
        msg = 'Command <{}> returned with error code: {}\n'
        msg = msg.format(e.cmd, e.returncode)
        print(msg)
        print('-' * 70)
        print(e.output.decode('utf8').strip())
        print('-' * 70)
        return None
    except FileNotFoundError as e:
        # Program not found.
        print(e)
        return None

    # Decode output and ensure it contains 'CropBox'.
    out = out.decode('utf8')
    assert 'CropBox' in out

    # Search for the line that starts with 'CropBox' and extract the values.
    for line in out.splitlines():
        if 'CropBox' in line:
            break

    # Split the line. This will result in plenty of empty list entries because
    # there are many blank spaces in that line. Remove those entries.
    line = line.strip()
    line = [_ for _ in line.split() if _ != '']

    # Drop the first because it is the 'CropBox' string.
    line = line[1:]

    # Convert the other entries to floats and return the result.
    box = [float(_) for _ in line]
    assert len(box) == 4
    return box


def computeMargins(fname_img, cropBox):
    """
    Return the PDF margins that would vertically center the \\\\rule block.

    This function assumes the image in ``fname`` does indeed feature a
    \\\\rule block to the left. If not, the result is unspecified.

    The ``cropBox`` is a list of four floats that denote the PDF dimensions in
    `big point` (bp). The values mean [left, top, right, bottom] and usually
    comes from :func:`getCropBox`.

    The return value is a Python string of four floats, unlike `cropBox``,
    which is a Python list of four floats. It does not denote absolute length
    etc, like the ``cropBox`` input, but rather the margin amount to add/remove
    on the respective side, in this order: [left, top, right, bottom]. This
    string can be passed directly to the `-margin` parameter of `pdfcrop`.

    :param **str** fname: name of image file.
    :param **list** cropBox: dimensions of PDF (eg. [0.0, 0.0, 87.11, 13.41])
    :return: Margins (eg. '[1.0 2.0, 3.0, 4.0]')
    :rtype: **str**
    """
    # Load the image.
    img = plt.imread(fname_img)

    # Grayscale images have only 2 dimensions, RGB(A) have a third to store the
    # colors. Remove them.
    if img.ndim > 2:
        # If there is an alpha channel, then remove it (ie. only retain the RGB
        # components).
        if img.shape[2] > 3:
            img = img[:, :, :3]

        # Convert to grayscale. The conversion need not be precise, because we
        # are looking for a black square, and black is always zero (although we
        # will allow for a small slack later on).
        img = np.sum(img, axis=2)
        img /= 3

    # For convenience.
    img_height, img_width = img.shape
    cb_width, cb_height = cropBox[2:4]

    # Find all (almost) black pixels. Then create a new matrix and set all
    # elements corresponding to a black pixel to 1.
    idx = np.nonzero(img < 0.1)
    img = np.zeros_like(img)
    img[idx] = 1
    del idx

    # Determine the width of the block. To do so, look for the first white
    # column, because Nobby will have inserted a white space after the block,
    # so there are *should* be several such. However, some fragments may well
    # be empty (eg. '\label{}' commands produce no visible text) so that no
    # white space remains. In that case, ...
    blk_width = -1
    for col in range(img_width):
        if sum(img[:, col]) == 0:
            blk_width = col
            break
    del col

    if blk_width == -1:
        return None

    # Double the width because the image contained a second rule of the same
    # width but zero height to ensure there is a proper space between the block
    # and the first character.
    blk_width = np.floor(1.95 * blk_width)

    # Determine vertical block boundaries. Once again, slice the block
    # vertically at half its width (determined just above), and look for the
    # index of the first/last black pixel in that column. The final values are
    # the distances from the top/bottom of the image.
    tmp = img[:, blk_width // 2]
    idx = np.nonzero(tmp)[0]
    gap_top, gap_bottom = idx[0], img_height - 1 - idx[-1]
    del tmp, idx

    # Determine how many rows at either the top or bottom of the image are
    # necessary to vertically center the block. Then convert this number of
    # matrix/image rows into a PDF margin based on the crop box height.
    num_rows = abs(gap_top - gap_bottom)
    delta_margin = num_rows * cb_height / img_height
    if gap_top > gap_bottom:
        bottom, top = delta_margin, 0
    elif gap_top < gap_bottom:
        bottom, top = 0, delta_margin
    else:
        top = bottom = 0

    # Compute the amount of PDF margin that corresponds to the block width.
    left = -blk_width * cb_width / img_width

    # Convert the four margins to a single string with four floats.
    out = ['{0:.2f}'.format(_) for _ in (left, top, 0, bottom)]
    return ' '.join(out)


def compileFragmentToImage(arg_tuple):
    """
    Convert ``frag`` into an SVG image and save it in ``target_dir``.

    To produce the SVG image, this function will first create a standalone
    LaTeX file based on the ``preamble`` and ``frag['tex']``, compile it into
    an auxiliary PDF file in the ``build_dir`` directory, and then convert it
    with `pdf2svg <http://www.cityinthesky.co.uk/opensource/pdf2svg/>`_

    The ``base_dir`` is the directory of the original LaTeX file. Knowing this
    directory is necessary because the fragment may include references to other
    files (eg. images) that are relative to that directory.

    The name of the final SVG depends on frag['placeholder'].

    The conversion to SVG suffers from cropping too much of the PDF image.
    While this removes all unnecessary white space, it also causes vertical
    alignment problems when the image is inserted in the HTML document. For
    instance, the cropped images for 'I' and 'y' have similar height, yet 'y'
    reaches lower than 'I'.

    To circumvent this problem a \\\\rule{1ex}{1ex} (ie a black box the size of
    an 'x' in the current font) precedes all fragments. This rule serves as a
    reference point to compute the PDF margins such that it sits precisely in
    the middle. For a good overview of the alignment options in HTML see
    `<http://www.maxdesign.com.au/articles/vertical-align/>`_.

    To compute the margin, the PDF is (temporarily) converted to a PDF and
    analyses as a NumPy array. The black box is easy to identify there, as is
    the computation of the required margin. The margin is extra space (not
    cropped space) at either the top or bottom such that the box is vertically
    centred. A similar process yields the width of the box, and the
    corresponding margin is removed from the image as well.

    This elaborate process requires these external tools:

    * `pdf2svg <http://www.cityinthesky.co.uk/opensource/pdf2svg/>`_
    * pdfinfo
    * `pdfcrop
      <http://manpages.ubuntu.com/manpages/gutsy/man1/pdfcrop.1.html>`_

    For compatibility with Python's process pools, this function takes only a
    single tuple argument, which it then expands to the actual arguments.

    :param **str** base_dir: directory of the source file.
    :param **str** build_dir: temporary directory to use for PDF creation.
    :param **str** target_dir: output directory of SVG file.
    :param **str** preamble: LaTeX preamble.
    :param **dict** frag: fragment data (typically from
        :func:`replaceFragments`)
    """
    # Expand the arguments.
    base_dir, build_dir, target_dir, preamble, frag = arg_tuple

    # Convenience.
    tex, frag_name = frag['tex'], frag['placeholder']

    # Create the document preamble. It consists of the original preamble plus
    # some special options that Nobby requires.
    tmp_tw = '\\addtolength{{\\textwidth}}{{{0:0.2f}cm}}'
    tmp_tw = tmp_tw.format(config.textwidth_addon)
    preamble += ('\n'
                 '\\pagestyle{empty}\n'
                 '\\addtolength{\\paperwidth}{20cm}\n'
                 '\\addtolength{\\paperheight}{20cm}\n'
                 + tmp_tw
                 )
    for key, value in frag['counters'].items():
        preamble += '\\setcounter{{{}}}{{{}}}\n'.format(key, value)
    del tmp_tw

    # Ensure the target- directory exists.
    try:
        os.mkdir(target_dir)
    except FileExistsError:
        pass

    # Name of fragment file (must be in same directory as the original source
    # code to ensure image include tags access the correct files).
    fname_tex = os.path.join(base_dir, frag_name + '.tex')

    # Name for SVG- and alternative image name.
    fname_svg = os.path.join(target_dir, frag_name + '.svg')
    fname_alt = os.path.join(target_dir, frag_name + '.' +
                             config.alt_image_format)

    # Do not compile already existing fragments.
    if config.skip_existing_fragments:
        if os.path.exists(fname_svg) or os.path.exists(fname_alt):
            return

    # Names of auxiliary files (all reside in a dedicated build directory).
    # Note that the crop file is always a PNG image, irrespective of the value
    # `config.alt_image_format`. The reason is that PNG does not employ lossy
    # image compression which and blurs the artificially added \rule block in
    # the process. This make the identification of that block easier (see
    # `computeMargins` function).
    tmp = os.path.join(build_dir, frag_name)
    fname_pdf = tmp + '.pdf'
    fname_crop = tmp + '_0_crop.pdf'
    fname_crop_aux = tmp + '_2_crop.pdf'
    fname_crop_png = fname_crop_aux[:-3] + 'png'
    del tmp

    def closeTex(data, scale):
        """
        Convenience function.
        """
        out = '\\begin{document}\n'
        out += '\pdfsetmatrix {%f 0 0 %f}\n' % (scale, scale)
        out += data + '\n\\end{document}'
        return out

    def removeStaleFiles():
        # Remove the temporary LaTeX file.
        try:
            os.remove(fname_tex)
        except FileNotFoundError:
            pass

    # Convenience.
    check_output = subprocess.check_output

    try:
        # Turn the fragment into a PDF.
        if frag['inline'] is True:
            # -----------------------------------------------------------------
            # A \rule the size of an 'x' precedes every fragment and will be
            # used as a reference to crop the PDF image such as to vertically
            # center it.
            # -----------------------------------------------------------------

            # This prefix contains a box that has exactly the height and width
            # of an 'x' character in the current font set.
            prefix = r'\rule{1ex}{1ex}\rule{1ex}{0ex}'

            # Create the LaTeX code for `frag` and write it to a temporary
            # file.
            tex = preamble + '\n'
            tex += closeTex(prefix + frag['tex'], config.pdf_scale)

            # Write the LaTeX code into a temporary file and compile it.
            open(fname_tex, 'w').write(tex)
            runPDFLaTeX(build_dir, fname_tex)
            del tex

            # Crop the PDF as tightly as possible.
            check_output(('pdfcrop', '--hires', fname_pdf, fname_crop_aux))

            # Ask 'pdfinfo' for the PDF size.
            cropBox = getCropBox(fname_crop_aux)
            if cropBox is None:
                return None

            # Turn the PDF into a PNG and determine how much to crop/extend the
            # margins to ensure the image is vertically centered.
            check_output(('convert', fname_crop_aux, fname_crop_png))
            marg = computeMargins(fname_crop_png, cropBox)
            if marg is None:
                open(fname_crop, 'w').write('')
            else:
                # Adjust the margins with pdfcrop.
                check_output(('pdfcrop', '--hires', '--margin',
                             marg, fname_crop_aux,  fname_crop))
            del cropBox, marg, prefix, fname_crop_png
        else:
            # -----------------------------------------------------------------
            # No special treatment is necessary for images that will go into a
            # dedicated paragraph.
            # -----------------------------------------------------------------
            tex = preamble + '\n' + closeTex(frag['tex'], config.pdf_scale)
            open(fname_tex, 'w').write(tex)
            runPDFLaTeX(build_dir, fname_tex)
            check_output(('pdfcrop', '--hires', fname_pdf, fname_crop))
            del tex

        # Convert PDF to SVG.
        if os.stat(fname_crop).st_size == 0:
            open(fname_svg, 'w').write(config.empty_svg)
        else:
            subprocess.check_output(('pdf2svg', fname_crop, fname_svg))

        # Replace the SVG file with the alternative image format if it exceeds
        # the max_svg_size threshold. However, only replace it if the
        # alternative image is indeed smaller.
        if os.stat(fname_svg).st_size > config.max_svg_size:
            subprocess.check_output(('convert', '-density', '120',
                                     fname_crop, fname_alt))

            # Only retain the alternative image if it is smaller than the SVG.
            if os.stat(fname_svg).st_size > os.stat(fname_alt).st_size:
                os.remove(fname_svg)
            else:
                os.remove(fname_alt)
        removeStaleFiles()
    except subprocess.CalledProcessError as e:
        # Process returned with non-zero exit code: dump the error message and
        # the complete process output.
        removeStaleFiles()
        msg = 'Command <{}> returned with error code: {}\n'
        msg = msg.format(e.cmd, e.returncode)
        print(msg)
        print('-' * 70)
        msg = 'Problematic Source code'
        print(' ' * (35 - len(msg) // 2), msg)
        print('-' * 70)
        if config.errtex_showfull:
            print(open(fname_tex, 'r').read())
        else:
            print(frag['tex'])
        print('-' * 70)
        raise e
    except FileNotFoundError as e:
        removeStaleFiles()
        raise e
    except AssertionError as e:
        removeStaleFiles()
        print('-' * 70)
        msg = 'Problematic Source code'
        print(' ' * (35 - len(msg) // 2), msg)
        print('-' * 70)
        if config.errtex_showfull:
            print(open(fname_tex, 'r').read())
        else:
            print(frag['tex'])
        print('-' * 70)
        raise e
    except (KeyboardInterrupt, SystemExit):
        removeStaleFiles()


def processFragments(preamble, html, fragments, path):
    """
    Convert all ``fragments`` to SVG images and update ``html``.

    Every element in ``fragments`` contains a self contained LaTeX fragment,
    save the common ``preamble``. Those fragments were created in
    :func:`createFragmentDescriptor`.

    This function is little more than a scheduler for the concurrent execution
    of :func:`compileFragmentToImage`. The ``num_processes`` variable
    determines how many processes to spawn. The compilation runs in the main
    thread if ``num_processes == 1`` (useful for debugging).

    :param *str* preamble: LaTeX preamble. Used to compile all fragments.
    :param *str* html: HTML code. Images are without suffix (eg. no '.svg').
    :param *list* fragments: Contains self contained LaTeX code fragments.
    :param *tuple* path: the usual set of path names.
    :rtype *str*:
    :return: ``html`` string with correct image extension in <img> tags.
    """
    # Generator: yield input tuple for compileFragmentToImage. The explicit
    # generate is only necessary because `multiprocessing.Pool` can only pass
    # along one argument. To compound this problem, the generator packs the
    # arguments into a tuple.
    gen = ((path.d_base, path.d_build, path.d_html, preamble, frag)
           for frag in fragments)

    # Compile every fragment.
    msg = 'Compiling {} fragments in {} processes'
    print(msg.format(len(fragments), config.num_processes))
    if config.num_processes == 1:
        # Run compilation in this very thread.
        for desc in gen:
            compileFragmentToImage(desc)
    else:
        # Push the compilation tasks into the available process pool.
        with multiprocessing.Pool(config.num_processes) as pool:
            if config.verbose:
                pool.map(compileFragmentToImage, gen)
            else:
                t0 = time.time()
                tot = len(fragments)
                sys.stdout.write('  Progress: ')
                sys.stdout.flush()
                per = ''
                proc = pool.imap_unordered(compileFragmentToImage, gen)
                for cnt, _ in enumerate(proc):
                    # Delete the previous percentage value and replace
                    # it with the new one.
                    sys.stdout.write('\b' * len(per))
                    per = '{}%'.format(int(100 * cnt / tot))
                    sys.stdout.write(per)
                    sys.stdout.flush()
                sys.stdout.write('\b' * len(per))
                print('done ({}s)'.format(int(time.time() - t0)))
                del t0, tot, per
    del gen

    # Remove auxiliary build directory.
    if os.path.exists(path.d_build) and not config.keep_builddir:
        shutil.rmtree(path.d_build)

    # -------------------------------------------------------------------------
    # The HTML code already contains the image tags and file names, but without
    # extensions (ie. no '.png' or '.svg'). Rectify.
    # -------------------------------------------------------------------------
    for frag in fragments:
        # Determine image file name without extension.
        placeholder = frag['placeholder']
        fname_ph = os.path.join(path.d_html, placeholder)

        # Determine from the file system if the image is SVG or the alternative
        # image format (usually 'png' or 'jpg').
        if os.path.exists(fname_ph + '.svg'):
            ext = '.svg'
        elif os.path.exists(fname_ph + '.' + config.alt_image_format):
            ext = '.' + config.alt_image_format
        else:
            print('Error: could not find fragment <{}>'.format(fname_ph))
            continue

        # Replace the original image name with the same one plus the correct
        # image format extension (eg. 'png' or 'svg').
        html = html.replace(placeholder, placeholder + ext)
    return html


# ----------------------------------------------------------------------------
#                            Prepare LaTeX Code
# ----------------------------------------------------------------------------


def sanitisePreamble(preamble):
    """
    Remove the font size specifier from ``\documentclass``.

    The purpose is to work around a potential problem with pdfcrop that
    occasionally manifested itself with 12pt fonts in combination with the
    --scale command line option (especially when the scale is < 1).

    Example:

    .. inline-python::

        import pprint, nobby
        preamble = '\\\\documentclass[10pt]{article}'
        out = nobby.sanitisePreamble(preamble)
        pprint.pprint(out)

    :param **str** preamble: LaTeX code.
    :return: same LaTeX code but without the xxpt in the documentclass (if one
        was present).
    :rtype: **str**
    """
    # Neutralise the comments.
    nc = neutraliseLaTeXComments(preamble)

    # Search for the documentclass tag. More specifically, the xxpt tag inside
    # the options (eg. 12pt).
    m = re.search(r'.*\\documentclass\[.*,{0,1} *\d+pt *,{0,1}.*?\]', nc)

    # No xxpt tag was found (or not documentclass, in which case this is really
    # not our problem but up the user to fix!).
    if m is None:
        return preamble

    # The span of the match. Extract the corresponding text from the original
    # ``preamble`` argument (ie not the neutralised one).
    start, stop = m.span()
    txt = preamble[start:stop]

    # Remove the font specification.
    out = re.sub(r',{0,1} *\d+pt *,{0,1}', '', txt)
    out = preamble[:start] + out + preamble[stop:]
    return out


def prettifyHTML(html):
    """
    Remove whitespace in empty lines and remove normal linebreaks.

    The purpose of removing whitespace in empty lines is cosmetic.

    The normal linebreaks need to be removed because Wordpress has a habit of
    otherwise enforcing them with <br> tags. I cannot think of a case where
    this is desirable because the line breaks stem most likely from the LaTeX
    code editor when it formatted the source code. From there it made its way
    to the HTML code. I deem the removal of these linebreaks safe.

    Example:

    .. inline-python::

        import pprint, nobby
        html = 'a\\n\\n \\n\\nb'
        out = nobby.prettifyHTML(html)
        pprint.pprint(out)

    :param **str** html: HTML code.
    :return: sane version of ``html`` without artificial line breaks.
    :rtype: **str**
    """
    # Remove all whitespace from empty lines.
    lines = [_ if len(_.strip()) > 0 else '' for _ in html.splitlines()]
    html = '\n'.join(lines)

    # ----------------------------------------------------------------------
    # Replace all single '\n' characters with whitespace. Replace all
    # sequences of '\n' with exactly two newlines.
    # ----------------------------------------------------------------------
    # Record the position of all '\n' sequences.
    pos = []
    for m in re.finditer(r'\n{2,}', html):
        pos.append((m.span()[0], m.group()))

    # Replace all newlines with whitespaces.
    html = re.sub(r'\n', ' ', html)

    # Re-insert the \n sequences. The net effect of this is that all single
    # newlines are now whitespaces whereas all sequences of newlines (ie. to
    # denote a paragraph) are preserved.
    for (start, txt) in pos:
        html = html[:start] + txt + html[start + len(txt):]

    # Reduce the sequences to exactly 2 newline characters.
    html = re.sub(r'\n{2,}', '\n\n', html)
    return html


def splitLaTeXDocument(document):
    """
    Return the preamble and document body of the LaTeX ``document``.

    The body does not contain the \begin{document} and \end{document}
    delimiters.

    Example:

    .. inline-python::

        import pprint, nobby
        document = 'preamble  \\\\begin{document}body \\\\end{document}'
        preamble, body = nobby.splitLaTeXDocument(document)
        pprint.pprint(preamble)
        pprint.pprint(body)

    :param **str** document: LaTeX document.
    :return: (preamble, body)
    :rtype: (**str**, **str**)
    """
    # Search for the \begin{document} and \end{document} tag. Return
    # immediately if one or both are amiss.
    m0 = re.search(r'\\begin *{document}', document)
    m1 = re.search(r'\\end *{document}', document)
    if m0 is None or m1 is None:
        return None, None

    # Extract the preamble and body. The body does not contain the actual
    # \begin{document} and \end{document} delimiters.
    m0_start, m0_stop = m0.span()
    m1_start, m1_stop = m1.span()
    preamble = document[:m0_start]
    body = document[m0_stop:m1_start]

    # Remove unnecessary white space and newlines.
    preamble = preamble.strip()
    body = body.strip()

    preamble = sanitisePreamble(preamble)
    return preamble, body


def neutraliseLaTeXComments(body):
    """
    Return a copy of ``body`` where all comments have been neutralised.

    The returned string has exactly the same length as ``body``. The main
    purpose of this function is to have an easy to parse reference version of
    the original document where the actual code is intact, and where none of
    the comments contains environments. The :func:`findEnvStandalone` makes use
    of this function.

    This function looks for LaTeX comments only. it ignores HTML comments.

    Example:

    .. inline-python::

        import nobby

        # Some LaTeX code.
        body = ('some %thing\\n'
                '% more \\n'
                'abc  % comment\\n')
        print(body)

        # Neutralise comments.
        out = nobby.neutraliseLaTeXComments(body)
        print(out)

    :param **str** body: LaTeX code.
    :return: ``body`` neutralised comments.
    :rtype: **str**
    """
    # Replace all escaped % symbols.
    copy = body.replace('\\%', 'xx')

    def repl(m):
        return ' ' * len(m.group())

    copy = re.sub(r'(%.*)', repl, copy)

    # Sanity check.
    assert len(copy) == len(body)
    return copy


def findLaTeXMetaInfo(preamble):
    """
    Return author and title specified in ``preamble``.

    Return 'No Title' and 'Unknown' for unspecified title or author,
    respectively.
    """
    # Remove all comments.
    preamble = neutraliseLaTeXComments(preamble)

    # Search for the first occurrence of the \title tag.
    m = re.search(r'\\title{(.*?)}', preamble)
    if m is None:
        title = 'No Title'
    else:
        title = m.groups()[0]

    # Search for the first occurrence of the \author tag.
    m = re.search(r'\\author{(.*?)}', preamble)
    if m is None:
        author = 'Unknown'
    else:
        author = m.groups()[0]

    return title, author


def compileWithCounters(preamble, body, path_names):
    """
    Return LaTeX counter values at various positions in source file ``body``.

    Nobby uses the LaTeX package 'newfile' to create an additional .nobby file
    during the compilation and populate it with counter values. The counter
    dump occurs before every environment specified in
    ``config.counter_dump_envs``. By default, these are all the standard
    environments like 'align', 'figure', ...

    After the compilation this function parses the .nobby file into a list of
    named tuples, each of which specifies the position in the ``body`` and the
    counter values at that point.

    The purpose of this procedure is to facilitate a continuous enumeration of
    equations, figures, etc. inside the SVG fragments. To this end
    :func:`createFragmentDescriptor` will inject the necessary LaTeX code to
    set the counters in the preamble of every fragment.

    :param *str* preamble: document preamble.
    :param *str* body: document body
    :rtype list:
    :return: list of named tuples. Each tuple notes the position in ``body``
      and holds a list of all counter values.
    """

    # ----------------------------------------------------------------------
    # Salt LaTeX file with counter dumps.
    # ----------------------------------------------------------------------
    # Augment the preamble with the commands to create an additional auxiliary
    # output file. If the tex file was 'foo.tex' then the auxiliary file will
    # be 'foo.nobby'.
    preamble += ('\n\\usepackage{newfile}\n'
                 '\\newoutputstream{nobby}\n'
                 '\\openoutputfile{\\jobname.nobby}{nobby}\n')

    # Separation character in .nobby file. This must be a character that LaTeX
    # would not allow in label names, and the backslash is one such character.
    sep = r'\\'

    def repl(m):
        # Prepend the original environment with a counter dump. The dump itself
        # utilises the LaTeX 'file' package to write information into a file.
        # In this case the file name ends in '.nobby' and contains the span of
        # the environment in the original document and the actual command to
        # write all counter values at the current position to the .nobby file.
        out = r'\addtostream{nobby}{'
        out += r'{1}{0}{2}{0}'.format(sep, m.span()[0], m.span()[1])
        for name in config.counter_names:
            out += '{1}{0} \\arabic{{{1}}}{0}'.format(sep, name)
        out += '}'
        return out + m.group()

    # Build a regular expression that matches any "\begin{env}" or "\macro"
    # where the 'env'- and 'macro' values are defined in the config file.
    envs = '|'.join(config.counter_dump_envs)
    macros = '|'.join(config.counter_dump_macros)
    pat1 = r'\\begin{(' + envs + ')}'
    pat2 = r'\\(' + macros + ')(?![a-zA-Z*])'

    # The complete regular expression has this structure:
    # (\\begin{(align|equation)}|\\(section|subsection)(?![a-zA-Z*]))
    pat = re.compile('({}|{})'.format(pat1, pat2))
    body = pat.sub(repl, body)
    del envs, macros, pat

    # ----------------------------------------------------------------------
    # Complete the LaTeX file and compile it.
    # ----------------------------------------------------------------------
    build_dir = path_names.d_build
    f_salted = '_nobby_counterdumps_' + path_names.f_tex
    p_salted = os.path.join(path_names.d_base, f_salted)

    tex = preamble + '\n\\begin{document}\n' + body
    tex += '\n\n\\closeoutputstream{nobby}\n\\end{document}\n'
    open(p_salted, 'w').write(tex)
    del tex
    try:
        runPDFLaTeX(build_dir, p_salted)
    except (subprocess.CalledProcessError, FileNotFoundError,
            AssertionError) as e:
        errmsg = ('Error: the salted document <{}> does not compile. This '
                  'is probably a bug - Abort.')
        print(errmsg.format(p_salted))
        print(e)
        sys.exit(1)

    # ----------------------------------------------------------------------
    # Parse the foo.nobby file. Each line has the same format, eg.
    # "40\53\section\1\subsection\0\subsubsection\0\equation\0\figure\0 ..."
    # The separation character ``sep`` in this example is '\'.
    # The first two numbers specify the span of the environment definition that
    # will succeed the counter dump, eg. the span of a '\begin{align}'. The
    # remaining entries are a ``sep`` separated list of counter- name and
    # value. The following code parses these lines into a list of named tuples.
    # ----------------------------------------------------------------------
    fname = os.path.join(build_dir, f_salted[:-3]) + 'nobby'
    NTCounter = collections.namedtuple('NTCounter', 'start stop counters')
    counters = []
    for line in open(fname, 'r').readlines():
        # Ignore empty lines.
        line = line.strip()
        if line == '':
            continue

        # Convert the ``sep`` separated list into a white space separated
        # list. Ensure there are no consecutive white spaces.
        line = re.sub(' *' + sep + ' *', sep, line)

        # Split the list into its constituents.
        line = line.strip().split(sep)

        # Extract the position where the counter dump occurred, along with the
        # counter values themselves, and assign them to the named tuple
        # NTCounter. Add that tuple to the output list.
        start, stop = int(line[0]), int(line[1])
        nt = NTCounter(start, stop, dict(zip(line[2::2], line[3::2])))
        counters.append(nt)

    # Remove the temporary tex file.
    os.remove(p_salted)
    return counters


# ----------------------------------------------------------------------------
#                               Miscellaneous
# ----------------------------------------------------------------------------

def checkDependencies():
    """
    Check that all required programs are installed.
    """
    def run(cmd):
        """
        Convenience function. It simply runs ``cmd`` and prints error messages,
        should there by any.
        """
        dn = subprocess.DEVNULL
        try:
            subprocess.call(cmd, stdout=dn, stderr=dn)
            out = True
        except subprocess.CalledProcessError as e:
            # Process return with non-zero error code.
            out = False
        except FileNotFoundError as e:
            # Specified program does not exist in the path on this computer.
            out = False
            print('Missing <{}>'.format(cmd))

        # Abort immediately if an error has occurred.
        if not out:
            sys.exit(1)

    # The programs required by Nobby.
    run('pdfinfo')
    run('pdf2svg')
    run('pdfcrop')
    run(('convert', '-version'))
    run(('pdflatex', '--version'))


def createHTMLMetaInfo(title, author):
    """
    Return meta information about Nobby and LaTeX document in a HTML comment.
    """
    txt = [
        '<!--',
        ' Converted with Nobby (https://olitheolix.com/doc/nobby/)',
        ' Title: {}'.format(title),
        ' Author: {}'.format(author),
        ' Date: {}'.format(time.strftime('%d %b %Y')),
        '-->']
    out = '\n'.join(txt)
    return out


def parseCmdline():
    """
    Parse the command line arguments.
    """
    # Instantiate parser and add program description.
    parser = argparse.ArgumentParser(
        description=('Convert LaTeX document to HTML and SVG images.\n'
                     'NOBBY 1.2 (GPL v3) Copyright (c) 2014 by Oliver Nagy\n'
                     'Documentation: https://olitheolix.com/doc/nobby/'),
        formatter_class=argparse.RawTextHelpFormatter)

    # Convenience.
    padd = parser.add_argument

    # Add the command line options.
    padd('--rebuild', '-r', action='store_true',
         help='Rebuild all fragments images')
    padd('--scale', '-s', type=float, metavar='S', default=config.pdf_scale,
         help='Scale all images by a factor of "S" (a float, S>0)')
    padd('--textwidth', type=float, metavar='W',
         default=config.textwidth_addon,
         help='Add \\addtolength{\\textwidth}{Wcm} to preamble')
    padd('--max-svg-size', metavar='N', type=int,
         default=config.max_svg_size,
         help='Replace SVG with bitmap if it exceeds N bytes')
    padd('--no-env-warning', action='store_true',
         help='Suppress warning about unknown environments')
    padd('--keep-build-dir', '-k', action='store_true',
         help='Do not delete the build directory')
    padd('--num-compile', default=config.num_compile_iter, metavar='N',
         type=int, help='Compile source file N times (default: N=3)')
    padd('--use-latexmk', action='store_true', default=config.use_latexmk,
         help='Use latexmk to determine number of compilations (slower)')
    padd('-j', type=int, default=config.num_processes,
         metavar='N', help='Number of concurrent compilation processes')
    padd('-o', type=str, default=None,
         metavar='dir', help='HTML output directory')
    padd('-v', action='store_true', default=config.verbose,
         help='Verbose')
    padd('-vv', action='store_true', default=config.errtex_showfull,
         help='More Verbose')
    padd('-w', action='store_true', default=False,
         help='Open HTML file in browser')
    padd('file', help='LaTeX file')

    # Let argparse parse the command line.
    args = parser.parse_args()

    # Add the command line options to the global ``config`` module.
    config.skip_existing_fragments = not args.rebuild
    config.pdf_scale = args.scale
    config.textwidth_addon = args.textwidth
    config.max_svg_size = args.max_svg_size
    config.show_unconverted_envs = not args.no_env_warning
    config.keep_builddir = args.keep_build_dir
    config.num_processes = args.j
    config.verbose = args.v
    config.errtex_showfull = args.vv
    config.html_dir = args.o
    config.num_compile_iter = args.num_compile
    config.use_latexmk = args.use_latexmk

    # Sanity check.
    if args.num_compile < 1:
        print('--num-compile must be a positive integer')
        sys.exit(1)

    if args.vv:
        config.verbose = True

    if args.w:
        config.launch_browser = True

    # Quit the program if the input file does not exist.
    fname = args.file
    if not os.path.exists(fname):
        print('File not found: {}'.format(fname))
        sys.exit(1)
    return fname


def definePathNames(fname_source):
    """
    Return all path names that Nobby may need in a dedicated tuple.

    The purpose of the returned tuple is to efficiently pass around file- and
    path names while maintaining code readability.

    :param *str* fname_source: source file (must be a LaTeX file).
    :rtype tuple:
    :return: tuple of path names.
    """
    # Split the file name into a path and name component. This is necessary
    # because several auxiliary files will be created and they need to be in
    # either the same path, or a deterministically related path.
    base_dir, fname_tex = os.path.split(fname_source)
    if base_dir == '':
        base_dir = './'

    # Define all directory- and file names. Store them in a named tuple.
    build_dir = '_build-' + os.path.splitext(fname_tex)[0]
    if config.html_dir is None:
        html_dir = 'html-' + os.path.splitext(fname_tex)[0]
    else:
        html_dir = config.html_dir
    build_dir = os.path.join(base_dir, build_dir)
    html_dir = os.path.join(base_dir, html_dir)
    fname_html = os.path.join(html_dir, fname_tex[:-3] + 'html')
    path_names = PathNames(fname_source, fname_tex, fname_html,
                           base_dir, build_dir, html_dir)
    del fname_source, fname_tex, fname_html, base_dir, build_dir, html_dir

    # Create the HTML output directory.
    try:
        os.mkdir(path_names.d_html)
    except FileExistsError:
        pass
    return path_names


# ----------------------------------------------------------------------------
#                               Main
# ----------------------------------------------------------------------------

def main():
    # Parse command line arguments and retrieve source file.
    fname_source = parseCmdline()

    # Ensure all dependencies are met.
    checkDependencies()
    if config.verbose:
        print('Passed dependency checks')

    # Determine all path- and file names Nobby needs in due course.
    path_names = definePathNames(fname_source)

    # Compile the original LaTeX document and abort if that fails.
    try:
        config.tex_output = runPDFLaTeX(path_names.d_build, fname_source)
    except (subprocess.CalledProcessError, FileNotFoundError,
            AssertionError) as e:
        errmsg = 'Error: the original document <{}> does not compile - Abort.'
        errmsg = errmsg.format(fname_source)
        print(errmsg)
        print(e)
        sys.exit(1)

    # Put a copy of the compiled PDF file to the HTML directory, in case the
    # HTML file wants to refer to the PDF version.
    src = os.path.join(path_names.d_build, path_names.f_tex[:-3] + 'pdf')
    dst = os.path.join(path_names.d_html, path_names.f_tex[:-3] + 'pdf')
    shutil.copy(src, dst)

    # Split LaTeX code into body and preamble.
    stream = open(path_names.f_source, 'r').read()
    preamble, body = splitLaTeXDocument(stream)

    # Add counter dumps to LaTeX file and recompile.
    config.counter_values = compileWithCounters(preamble, body, path_names)
    if config.verbose:
        print('Successfully extracted LaTeX counters.')

    # Obtain meta information like document- author and title.
    title, author = findLaTeXMetaInfo(preamble)

    # Find all LaTeX environment delimiters known to Nobby (eg. '$',
    # '\begin{}', etc) and prune it to remove nested environments.
    delim_list = findDelimiters(body)
    delim_list = pruneDelimiters(delim_list, plugins.plugins)

    # Convert the LaTeX code into a tree based on the position of the
    # environment delimiters from the previous step.
    tree = buildTree(body, delim_list)

    # Convert the tree nodes into HTML code and a list of independent
    # fragments.
    fragments = []
    html = convertTreeToHTML(tree, fragments, plugins.plugins)
    if config.verbose:
        if len(no_plugins) > 0:
            print('Missing plugins for:')
            for _ in no_plugins:
                print('  {}: <{}>'.format(*_))

    # Compile all LaTeX fragments into SVG images and add the correct file
    # extension (eg. 'PNG' or 'SVG') to all <img> tags in the HTML code.
    html = processFragments(preamble, html, fragments, path_names)

    # Remove all artificial line breaks to prevent Wordpress from enforcing
    # them.
    html = prettifyHTML(html)

    # Insert line breaks around every paragraph to improve the readability of
    # the HTML file.
    html = re.sub(r'<p>', '\n\n<p>\n\n', html)

    # Prefix the HTML code with the meta information from the LaTeX code.
    html = createHTMLMetaInfo(title, author) + html

    # Save the HTML file.
    open(path_names.f_html, 'w').write(html)

    # Open the HTML file in Firefox, if requested via the -wb command line
    # argument.
    if config.launch_browser:
        wb = webbrowser.get(None)
        wb.open(path_names.f_html, new=2, autoraise=True)


if __name__ == '__main__':
    main()
