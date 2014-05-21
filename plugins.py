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

# Global variables for the section counters. The plugins for section,
# subsection and subsubsection will increase them accordingly. The enumeration
# will be consistent with LaTeX' internal one if no sectioning commands occur
# inside environments included as SVG images.
section_counters = {'s1': 0, 's2': 0, 's3': 0}

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


def itemize(nodes):
    ret = '<ul>', nodes, '</ul>'
    return ret


def nobby_enumerate(nodes):
    ret = '<ol>', nodes, '</ol>'
    return ret


def item(nodes):
    ret = '<li>', nodes
    return ret


def chapter(nodes):
    """
    Chapters get the same heading as sections. This is for simplicity, and also
    because Nobby is meant for articles, not reports, books, etc.
    """
    ret = '<h1>', nodes, '</h1>'
    return ret


def section(nodes):
    assert len(nodes) > 0
    label_name = nodes[0].body

    global section_counters
    section_counters['s1'] += 1
    section_counters['s2'] = 0
    section_counters['s3'] = 0

    enum = '{}  '.format(section_counters['s1'])
    ret = '<h1>' + enum, nodes, '</h1>'
    return ret


def subsection(nodes):
    global section_counters
    section_counters['s2'] += 1
    section_counters['s3'] = 0

    enum = '{}.{}  '.format(section_counters['s1'], section_counters['s2'])
    ret = '<h2>' + enum, nodes, '</h2>'
    return ret


def subsubsection(nodes):
    global section_counters
    section_counters['s3'] += 1
    enum = '{}.{}.{}  '.format(section_counters['s1'], section_counters['s2'],
                               section_counters['s3'])

    ret = '<h3>' + enum, nodes, '</h3>'
    return ret


def comment(nodes):
    ret = '<!--', nodes, '-->\n'
    return ret


def label(nodes):
    ret = '<a name="{}"></a>'.format(nodes[0].body)
    return ret


def hyperref(nodes):
    assert len(nodes) >= 2
    labelname = nodes[0].body
    linktext = nodes[1].body

    # Remove the [] brackets from the body of the first text node. No such
    # precaution is necessary with the second node, because it is natively a
    # curly node.
    labelname = labelname[1:-1]
    ret = '<a href="#{}">{}</a>'.format(labelname, linktext)
    return ret


def href(nodes):
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


def ref(nodes):
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


def emph(nodes):
    ret = '<em>', nodes, '</em>'
    return ret


def ldots(nodes):
    return '...', nodes


def textbf(nodes):
    ret = '<b>', nodes, '</b>'
    return ret


def texttt(nodes):
    ret = '<tt>', nodes, '</tt>'
    return ret


def ignore_macro_arg0(nodes):
    # Void the macro. Do not consume any arguments.
    return nodes


def ignore_macro_arg1(nodes):
    # Void the macro. Consume one argument.
    return nodes[1:]


def ignore_macro_arg2(nodes):
    # Void the macro. Consume two arguments.
    return nodes[2:]


def newpage(nodes):
    return '<p>', nodes


def textbackslash(nodes):
    return '\\', nodes


def url(nodes):
    # Sanity check.
    assert len(nodes) > 0

    # The node body contains the text of the entire text of the first argument.
    body = nodes[0].body

    # Form the HTML anchor tag.
    return '<a href="#{0}">{0}</a>'.format(body)


# ---------------------------------------------------------------------------
# Place all plugins in this dictionary. The key is the name of the macro- or
# environment the plugin processes, and the value is the function.
# ---------------------------------------------------------------------------
plugins = {
    'itemize': itemize,
    'enumerate': nobby_enumerate,
    'item': item,
    'chapter': chapter,
    'section': section,
    'subsection': subsection,
    'subsubsection': subsubsection,
    'comment_': comment,
    'label': label,
    'hyperref': hyperref,
    'ref': ref,
    'href': href,
    'emph': emph,
    'ldots': ldots,
    'textbf': textbf,
    'texttt': texttt,
    'maketitle': ignore_macro_arg0,
    'noindent': ignore_macro_arg0,
    'footnote': ignore_macro_arg1,
    'rule': ignore_macro_arg2,
    'newpage': newpage,
    'textbackslash': textbackslash,
    'url': url,
    }
