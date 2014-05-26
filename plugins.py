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

import re
import config
import IPython

ipshell = IPython.embed

# -----------------------------------------------------------------------------
# Plugins are normal function that take one argument. That argument is always
# a list of TreeNode instances (see nobby.py). The list may be empty.
#
# To register a plugin with Nobby, add it to ``plugins`` dictionary at the
# end of this file.
#
# Refer to the documentation for more information about plugins.
# -----------------------------------------------------------------------------


def itemize(nodes, parent):
    ret = '<ul>', nodes, '</ul>'
    return ret


def nobby_enumerate(nodes, parent):
    ret = '<ol>', nodes, '</ol>'
    return ret


def item(nodes, parent):
    ret = '<li>', nodes
    return ret


def chapter(nodes, parent):
    """
    Chapters get the same heading as sections. This is for simplicity, and also
    because Nobby is meant for articles, not reports, books, etc.
    """
    ret = '<h1>', nodes, '</h1>'
    return ret


def section_star(nodes, parent):
    ret = '<h1>', nodes, '</h1>'
    return ret


def section(nodes, parent):
    assert len(nodes) > 0
    label_name = nodes[0].body

    # LaTeX' Section counter. Add +1 because the Nobby recorded the counter
    # value before the \section command.
    cnt = int(parent.counters['section']) + 1

    # Create the heading with number and name (eg. '1 Introduction').
    enum = '{}  '.format(cnt)
    ret = '<h1>' + enum, nodes, '</h1>'
    return ret


def subsection_star(nodes, parent):
    ret = '<h2>', nodes, '</h2>'
    return ret


def subsection(nodes, parent):
    # Get LaTeX' Section and Sub-Section counter. Add +1 to the sub-section
    # counter because Nobby recorded it just before the \subsection
    # command. The +1 is unnecessary for the 'section' counter because the
    # \subsection macro does not increment it.
    cnt_sec = int(parent.counters['section'])
    cnt_subsec = int(parent.counters['subsection']) + 1

    # Create the heading with number and name (eg. '1.1 Introduction').
    enum = '{}.{}  '.format(cnt_sec, cnt_subsec)
    ret = '<h2>' + enum, nodes, '</h2>'
    return ret


def subsubsection_star(nodes, parent):
    ret = '<h3>', nodes, '</h3>'
    return ret


def subsubsection(nodes, parent):
    # Get LaTeX' Section, Sub-Section, and Sub-Sub-Section counter. Add +1 to
    # the sub-sub-section counter because Nobby recorded it just before the
    # \subsubsection command. The +1 is unnecessary for the other two counters
    # because the \subsubsection macro does not increment them.
    cnt_sec = int(parent.counters['section'])
    cnt_subsec = int(parent.counters['subsection'])
    cnt_subsubsec = int(parent.counters['subsubsection']) + 1

    # Create the heading with number and name (eg. '1.1.1 Introduction').
    enum = '{}.{}.{}  '.format(cnt_sec, cnt_subsec, cnt_subsubsec)

    ret = '<h3>' + enum, nodes, '</h3>'
    return ret


def comment(nodes, parent):
    ret = '<!--', nodes, '-->\n'
    return ret


def label(nodes, parent):
    ret = '<a name="{}"></a>'.format(nodes[0].body)
    return ret


def hyperref(nodes, parent):
    assert len(nodes) >= 2
    labelname = nodes[0].body
    linktext = nodes[1].body

    # Remove the [] brackets from the body of the first text node. No such
    # precaution is necessary with the second node, because it is natively a
    # curly node.
    labelname = labelname[1:-1]
    ret = '<a href="#{}">{}</a>'.format(labelname, linktext)
    return ret


def href(nodes, parent):
    """
    This is almost identical to hyperref except that it requires two mandatory
    arguments, instead of only one. The first node is therefore also a curly
    node and [] brackets need removal.
    """
    assert len(nodes) >= 2
    labelname = nodes[0].body
    linktext = nodes[1].body
    ret = '<a href="{}">{}</a>'.format(labelname, linktext)
    return ret


def ref(nodes, parent):
    """
    Parse the .aux content for the corresponding label and return it.
    """
    assert len(nodes) > 0
    label_name = nodes[0].body
    p = re.compile(r'\\newlabel{' + label_name + r'}{{(.*?)}{(.*?)}')
    m = p.search(config.tex_output.aux)
    if m is None:
        print('Warning: cannot find label <{}>'.format(label_name))
        return nodes
    else:
        label_number = m.groups()[0]
        tag = '<a href="#{}">{}</a>'.format(label_name, label_number)
        return tag, nodes[1:]


def emph(nodes, parent):
    ret = '<em>', nodes, '</em>'
    return ret


def ldots(nodes, parent):
    return '...', nodes


def textbf(nodes, parent):
    ret = '<b>', nodes, '</b>'
    return ret


def texttt(nodes, parent):
    ret = '<tt>', nodes, '</tt>'
    return ret


def ignore_macro_arg0(nodes, parent):
    # Void the macro. Do not consume any arguments.
    return nodes


def ignore_macro_arg1(nodes, parent):
    # Void the macro. Consume one argument.
    return nodes[1:]


def ignore_macro_arg2(nodes, parent):
    # Void the macro. Consume two arguments.
    return nodes[2:]


def newpage(nodes, parent):
    return '<p>', nodes


def textbackslash(nodes, parent):
    return '\\', nodes


def theorem(nodes, parent):
    # Start of theorem environment. Infer environment name from the node
    # because this plugin services all environments defined via the
    # ``\newtheorem`` command.
    env_name = parent.name.capitalize()

    # Access the LaTeX counter values to determine the theorem number.
    cnt = int(parent.counters[parent.name]) + 1

    # Add the count to the displayed environment name to obtain eg. 'Lemma 3'.
    env_name += ' {}'.format(cnt)

    # Theorems get their own paragraph. The eg 'Lemma 3' name is in bold.
    ret = '<p><div><blockquote><b>' + env_name + '</b>: '

    # Extract the optional theorem argument if present. Optional arguments
    # are enclosed inside square brackets, which Nobby treats as normal text
    # (unlike curly braces). Therefore, use a regular expression to identify
    # the argument.
    if (len(nodes) > 0):
        m = re.match(r'^\[(.*?)\]', nodes[0].body)
        if m is not None:
            # Found an optional argument (ie. something inside square
            # brackets): treat it as the theorem name.
            ret += m.groups()[0]

            # Remove the span of the theorem name from the node body.
            _, stop = m.span()
            nodes[0].body = nodes[0].body[stop+2:]

    # Put the theorem content itself into a blockquote environment.
    return ret + '<br><i>', nodes, '</i></blockquote></div><p>'


def proof(nodes, parent):
    return '<div><i>Proof: ', nodes, '</i></div><p>'


def url(nodes, parent):
    # Sanity check.
    assert len(nodes) > 0

    # The node body contains the entire text of the first argument.
    body = nodes[0].body

    # Form the HTML anchor tag.
    return '<a href="#{0}">{0}</a>'.format(body)


# ---------------------------------------------------------------------------
# Place all plugins in this dictionary. The key is the name of the macro- or
# environment the plugin processes, and the value is the function.
# ---------------------------------------------------------------------------
plugins = {
    'chapter': chapter,
    'comment_': comment,
    'emph': emph,
    'enumerate': nobby_enumerate,
    'footnote': ignore_macro_arg1,
    'href': href,
    'hyperref': hyperref,
    'item': item,
    'itemize': itemize,
    'label': label,
    'ldots': ldots,
    'maketitle': ignore_macro_arg0,
    'newpage': newpage,
    'noindent': ignore_macro_arg0,
    'ref': ref,
    'rule': ignore_macro_arg2,
    'section': section,
    'section*': section_star,
    'subsection': subsection,
    'subsection*': subsection_star,
    'subsubsection': subsubsection,
    'subsubsection*': subsubsection_star,
    'lemma': theorem,
    'theorem': theorem,
    'example': theorem,
    'corollary': theorem,
    'definition': theorem,
    'proof': proof,
    'textbackslash': textbackslash,
    'textbf': textbf,
    'texttt': texttt,
    'url': url,
    }
