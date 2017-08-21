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

import config
import nobby
import IPython

ipshell = IPython.embed
config.ph_format = '|{0}-{1:d}|'
config.tag_format = '{}'

findComments = nobby.findComments
findBeginEnd = nobby.findBeginEnd
findCurly = nobby.findCurly
findDollar = nobby.findDollar
findNewline = nobby.findNewline
findMacros = nobby.findMacros
findDelimiters = nobby.findDelimiters
pruneDelimiters = nobby.pruneDelimiters
convertTreeToHTML = nobby.convertTreeToHTML
convertTextToHTML = nobby.convertTextToHTML
buildTree = nobby.buildTree
splitLaTeXDocument = nobby.splitLaTeXDocument
sanitisePreamble = nobby.sanitisePreamble
prettifyHTML = nobby.prettifyHTML
neutraliseLaTeXComments = nobby.neutraliseLaTeXComments


class TestNobby():
    def test_splitLaTeXDocument(self):
        stream = ' preamble  \\begin{document}\nbody \n\\end{document}  '

        preamble, body = splitLaTeXDocument(stream)
        assert preamble == 'preamble'
        assert body == 'body'

        stream = ' preamble  \\begin{document}body \\end{documentt}'

        preamble, body = splitLaTeXDocument(stream)
        assert preamble is None
        assert body is None

    def test_sanitisePreamble(self):
        stream = ' \\documentclass[onepage, 10pt]{article}'
        preamble = sanitisePreamble(stream)
        assert preamble == ' \\documentclass[onepage]{article}'

        stream = '\\documentclass[10pt,onepage]{article}'
        preamble = sanitisePreamble(stream)
        assert preamble == '\\documentclass[onepage]{article}'

        stream = '\\documentclass[10pt]{article}'
        preamble = sanitisePreamble(stream)
        assert preamble == '\\documentclass[]{article}'

        stream = '\\documentclass[onepage]{article}'
        preamble = sanitisePreamble(stream)
        assert preamble == '\\documentclass[onepage]{article}'

        stream = '%\\documentclass[onepage,10pt]{article}'
        preamble = sanitisePreamble(stream)
        assert preamble == '%\\documentclass[onepage,10pt]{article}'

        stream = ('%\\documentclass[onepage,10pt]{article}\n'
                  '\\documentclass[onepage,11pt]{article}\n'
                  '%\\documentclass[onepage,12pt]{article}\n')
        preamble = sanitisePreamble(stream)
        assert preamble == ('%\\documentclass[onepage,10pt]{article}\n'
                            '\\documentclass[onepage]{article}\n'
                            '%\\documentclass[onepage,12pt]{article}\n')

    def test_prettifyHTML(self):
        body = "a\nb"
        out = prettifyHTML(body)
        assert out == 'a b'

        body = "a \nb"
        out = prettifyHTML(body)
        assert out == 'a  b'

        body = "a\n b"
        out = prettifyHTML(body)
        assert out == 'a  b'

        body = "a\n\nb"
        out = prettifyHTML(body)
        assert out == 'a\n\nb'

        body = "a\n\n b"
        out = prettifyHTML(body)
        assert out == 'a\n\n b'

        body = "a \n\nb"
        out = prettifyHTML(body)
        assert out == 'a \n\nb'

        body = "a\n\n\nb"
        out = prettifyHTML(body)
        assert out == 'a\n\nb'

        body = "a\n\n\n\nb"
        out = prettifyHTML(body)
        assert out == 'a\n\nb'

        body = "a\n\n \n\nb"
        out = prettifyHTML(body)
        assert out == 'a\n\nb'

    def test_neutraliseLaTeXComments(self):
        body = 'some thing\n'
        out = neutraliseLaTeXComments(body)
        assert len(out) == len(body)
        assert out == body

        body = 'some % comment\n'
        out = neutraliseLaTeXComments(body)
        assert len(out) == len(body)
        assert out == 'some ' + ' ' * len('% comment') + '\n'

        body = ('some %thing\n'
                '% more \n'
                'abc  % comment\n')
        out = neutraliseLaTeXComments(body)
        assert len(out) == len(body)
        assert out == ('some ' + ' ' * len('%thing') + '\n' +
                       ' ' * len('% more ') + '\n' +
                       'abc  ' + ' ' * len('% comment') + '\n')

        body = '100\\% % something\n'
        out = neutraliseLaTeXComments(body)
        assert out == '100xx ' + ' ' * len('% something') + '\n'
        assert len(out) == len(body)

    def test_findComments(self):
        body = 'p%c\n'
        _, out = findComments(body)

        # Convert the dictionary to a sorted list.
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 2
        assert out[0] == ((1, 2), True,  '%', None)
        assert out[1] == ((3, 4), False, '%', None)

        body = '% foo\n'
        _, out = findComments(body)
        # Convert the dictionary to a sorted list.
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 2
        assert out[0] == ((0, 1), True,  '%', None)
        assert out[1] == ((5, 6), False, '%', None)

        body = ' % indented\n'
        _, out = findComments(body)
        # Convert the dictionary to a sorted list.
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 2
        assert out[0] == ((1, 2), True,  '%', None)
        assert out[1] == ((11, 12), False, '%', None)

        body = 'fake \\% c\n'
        _, out = findComments(body)
        # Convert the dictionary to a sorted list.
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 0

    def test_findBeginEnd(self):
        body = r'\begin{foo}bar\end{foo}'
        _, out = findBeginEnd(body)

        # Convert the dictionary to a sorted list.
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 2
        assert out[0] == ((0, 11), True, 'env', 'foo')
        assert out[1] == ((14, 23), False, 'env', 'foo')

    def test_findCurly(self):
        body = 'a {b} c {}'
        _, out = findCurly(body)

        # Convert the dictionary to a sorted list.
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 4
        assert out[0] == ((2, 3), True,  '{', None)
        assert out[1] == ((4, 5), False, '}', None)
        assert out[2] == ((8, 9), True,  '{', None)
        assert out[3] == ((9, 10), False, '}', None)

    def test_findDollar(self):
        body = 'a $b$ c \$'
        _, out = findDollar(body)

        # Convert the dictionary to a sorted list.
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 2
        assert out[0] == ((2, 3), True,  '$', None)
        assert out[1] == ((4, 5), False, '$', None)

    def test_findNewline(self):
        body = '\\\\'
        _, out = findNewline(body)
        assert out[0] == ((0, 2), None, 'macro', '\\')

    def test_findMacros(self):
        body = r'\ldots '

        # Find macros and convert the delimiter dictionary to a sorted list.
        _, out = findMacros(body)
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 1
        assert out[0] == ((0, 6), None, 'macro', r'ldots')
        start, stop = out[0].span
        assert body[start:stop] == r'\ldots'

        # Make sure that findMacro does not pick up escaped special LaTeX
        # symbols.
        body = r'\# \$ \% \&  \^ \_ \{ \} \~'
        _, out = findMacros(body)
        assert len(out) == 0

        body = r'\ldots \vdots '
        # Find macros and convert the delimiter dictionary to a sorted list.
        _, out = findMacros(body)
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 2
        assert out[0] == ((0, 6), None, 'macro', 'ldots')
        assert out[1] == ((7, 13), None, 'macro', 'vdots')
        start, stop = out[0].span
        assert body[start:stop] == r'\ldots'
        start, stop = out[1].span
        assert body[start:stop] == r'\vdots'

        body = r'\section* blah'
        # Find macros and convert the delimiter dictionary to a sorted list.
        _, out = findMacros(body)
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 1
        assert out[0] == ((0, 9), None, 'macro', 'section*')
        start, stop = out[0].span
        assert body[start:stop] == r'\section*'

    def test_findMacros_single(self):
        bodies = [r'\ldots ', r'\ldots1', r'\ldots~', r'\ldots.',
                  r'\ldots{', r'\ldots}', r'\ldots[', r'\ldots]',
                  r'\ldots(', r'\ldots)', '\\ldots\\']

        for body in bodies:
            _, out = findMacros(body)
            assert out[0] == ((0, 6), None, 'macro', 'ldots')

    def test_findMacros_multi(self):
        body = r'\ldots\vdots '

        # Find delimiters and convert the returned dictionary to a list.
        _, out = findMacros(body)
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 2
        assert out[0] == ((0, 6), None, 'macro', 'ldots')
        assert out[1] == ((6, 12), None, 'macro', 'vdots')

        body = r'\ldots \vdots '

        # Find delimiters and convert the returned dictionary to a list.
        _, out = findMacros(body)
        out = [out[_] for _ in sorted(out)]

        assert len(out) == 2
        assert out[0] == ((0, 6), None, 'macro', 'ldots')
        assert out[1] == ((7, 13), None, 'macro', 'vdots')

    def test_findDelimiters_text(self):
        body = 'normal\n'
        out = findDelimiters(body)
        assert len(out) == 2
        assert out[0] == ((0, 0), True, 'text', None)
        assert out[1] == ((7, 7), False, 'text', None)

    def test_findDelimiters_escaped(self):
        body = r'a {b\$ c \{}'
        out = findDelimiters(body)
        assert len(out) == 6
        assert out[0] == ((0, 0), True,  'text', None)
        assert out[1] == ((2, 2), False, 'text', None)
        assert out[2] == ((2, 3), True,  '{', None)
        assert out[3] == ((3, 3), True,  'text', None)
        assert out[4] == ((11, 11), False, 'text', None)
        assert out[5] == ((11, 12), False, '}', None)

    def test_findDelimiters_mixed(self):
        body = r'\ldots \\\vdots '
        out = findDelimiters(body)
        assert len(out) == 7
        assert out[0] == ((0, 6), None, 'macro', r'ldots')
        assert out[1] == ((6, 6), True, 'text', None)
        assert out[2] == ((7, 7), False, 'text', None)
        assert out[3] == ((7, 9), None, 'macro', '\\')
        assert out[4] == ((9, 15), None, 'macro', 'vdots')
        assert out[5] == ((15, 15), True, 'text', None)
        assert out[6] == ((16, 16), False, 'text', None)

    def test_pruneDelimiters(self):
        body = 'blah'
        out = findDelimiters(body)
        out = pruneDelimiters(out)
        assert len(out) == 2

        body = '{foo}'
        out = findDelimiters(body)
        out = pruneDelimiters(out)
        assert len(out) == 4

        body = 'foo $x$ bar '
        out = findDelimiters(body)
        out = pruneDelimiters(out)
        assert len(out) == 6

        body = 'foo $$x$$ bar '
        out = findDelimiters(body)
        out = pruneDelimiters(out)
        assert len(out) == 6

        body = 'foo $$x={1}$$ bar '
        out = findDelimiters(body)
        out = pruneDelimiters(out)
        assert len(out) == 6

        body = 'foo $$x={{1}}$$ bar '
        out = findDelimiters(body)
        out = pruneDelimiters(out)
        assert len(out) == 6

        body = r'foo \begin{bar} x \end{bar}'
        out = findDelimiters(body)
        out = pruneDelimiters(out)
        assert len(out) == 4

        body = r'foo \begin{bar} $x$ \end{bar}'
        out = findDelimiters(body)
        out = pruneDelimiters(out)
        assert len(out) == 4

        body = r'foo \begin{bar} $x$ \end{bar}'
        out = findDelimiters(body)
        out = pruneDelimiters(out, plugins=['bar'])
        assert len(out) == 10

        body = r'foo \begin{foo}\begin{bar}\end{bar}\end{foo}'
        out = findDelimiters(body)
        out = pruneDelimiters(out, plugins=['bar'])
        assert len(out) == 4

        body = r'foo \begin{bar}\begin{bar}\end{bar}\end{bar}'
        out = findDelimiters(body)
        out = pruneDelimiters(out, plugins=['bar'])
        assert len(out) == 6

        body = r'\begin{bar}\begin{foo}\begin{bar}\end{bar}\end{foo}\end{bar}'
        body = r'foo ' + body
        out = findDelimiters(body)
        out = pruneDelimiters(out, plugins=['bar'])
        assert len(out) == 6

    def test_buildTree_text(self):
        body = 'a\n'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)

        assert len(out.kids) == 1
        c0 = out.kids[0]
        assert c0.type == 'text'
        assert c0.span == (0, 2)
        assert c0.name == 'text_'
        assert c0.body == 'a\n'

        body = 'a'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)

        assert len(out.kids) == 1
        c0 = out.kids[0]
        assert c0.type == 'text'
        assert c0.span == (0, 1)
        assert c0.name == 'text_'
        assert c0.body == 'a'

        body = '$x$a'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)

        assert len(out.kids) == 2
        c0, c1 = out.kids
        assert c0.type == '$'
        assert c0.span == (0, 3)
        assert c0.name == 'dollar1_'
        assert c0.body == 'x'
        assert c1.type == 'text'
        assert c1.span == (3, 4)
        assert c1.name == 'text_'
        assert c1.body == 'a'

    def test_buildTree_macroonly_multi(self):
        body = r'\ldots \vdots '
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)

        assert len(out.kids) == 4
        c0, c1, c2, c3 = out.kids
        assert c0.type == 'macro'
        assert c1.type == 'text'
        assert c2.type == 'macro'
        assert c3.type == 'text'
        assert c0.span == (0, 6)
        assert c1.span == (6, 7)
        assert c2.span == (7, len(body) - 1)
        assert c0.name == 'ldots'
        assert c0.body == ''
        assert c1.body == ' '
        assert c2.name == 'vdots'
        assert c2.body == ''

        body = r'\ldots\vdots '
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)

        assert len(out.kids) == 3
        c0, c1, c2 = out.kids
        assert c0.type == 'macro'
        assert c0.span == (0, 6)
        assert c0.name == 'ldots'
        assert c0.body == ''
        assert c1.type == 'macro'
        assert c1.span == (6, 12)
        assert c1.name == 'vdots'
        assert c1.body == ''
        assert c2.type == 'text'

    def test_buildTree_braceonly(self):
        body = '{a0} {a1}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)

        assert len(out.kids) == 3
        c0, c1, c2 = out.kids
        assert c0.type == c2.type == '{'
        assert c1.type == 'text'
        assert c0.parent is out
        assert c1.parent is out
        assert c2.parent is out
        assert c0.span == (0, 4)
        assert c1.span == (4, 5)
        assert c2.span == (5, 9)
        assert c0.body == 'a0'
        assert c1.body == ' '
        assert c2.body == 'a1'

        body = '{{a0} {a1}}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)

        # First node has only one child.
        assert len(out.kids) == 1
        node = out.kids[0]

        # Second node has two children.
        c0, c1, c2 = node.kids
        assert c0.type == c2.type == '{'
        assert c0.span == (1, 5)
        assert c1.span == (5, 6)
        assert c2.span == (6, 10)
        assert c0.body == 'a0'
        assert c1.body == ' '
        assert c2.body == 'a1'

    def test_buildTree_dollaronly(self):
        body = '$a0$ $a1$'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)

        assert len(out.kids) == 3
        c0, c1, c2 = out.kids
        assert c0.type == c2.type == '$'
        assert c1.type == 'text'
        assert c0.parent is out
        assert c1.parent is out
        assert c2.parent is out
        assert c0.span == (0, 4)
        assert c1.span == (4, 5)
        assert c2.span == (5, 9)
        assert c0.body == 'a0'
        assert c1.body == ' '
        assert c2.body == 'a1'

        body = '$$a0$$ $$a1$$'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)
        c0, c1, c2 = out.kids
        assert c0.type == c2.type == '$$'
        assert c1.type == 'text'
        assert c0.parent is out
        assert c1.parent is out
        assert c2.parent is out
        assert c0.span == (0, 6)
        assert c1.span == (6, 7)
        assert c2.span == (7, 13)
        assert c0.body == 'a0'
        assert c1.body == ' '
        assert c2.body == 'a1'

    def test_buildTree_beginendonly(self):
        body = r'\begin{foo}bar\end{foo}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)

        assert len(out.kids) == 1
        c0 = out.kids[0]
        assert c0.type == 'env'
        assert c0.name == 'foo'
        assert c0.parent is out
        assert c0.span == (0, len(body))
        assert c0.body == 'bar'

    def test_buildTree_mixed_flat(self):
        body = 'a0 $a1$ {a2}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)

        assert len(out.kids) == 4
        c0, c1, c2, c3 = out.kids
        assert c0.type == 'text'
        assert c0.body == 'a0 '
        assert c1.type == '$'
        assert c1.body == 'a1'
        assert c2.type == 'text'
        assert c2.body == ' '
        assert c3.type == '{'
        assert c3.body == 'a2'

    def test_buildTree_mixed_nested(self):
        body = '{a0 {$a1$}}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        out = buildTree(body, delim_list)

        assert len(out.kids) == 1
        c0 = out.kids[0]
        assert c0.type == '{'
        assert c0.body == 'a0 {$a1$}'

        c0, c1 = c0.kids
        assert c0.type == 'text'
        assert c0.body == 'a0 '
        assert c1.type == '{'
        assert c1.body == '$a1$'

        c0 = c1.kids[0]
        assert c0.type == '$'
        assert c0.body == 'a1'

    def test_convertTreeToHTML_macro_noplugin(self):
        body = r'\fbox{a}b '
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        frags = []
        html = convertTreeToHTML(root, frags, {})
        assert html == '|fbox-0|b '
        assert len(frags) == 1
        assert frags[0]['tex'] == r'\fbox{a}'

        body = r'{{\textnormal{norma tex}}}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        frags = []
        html = convertTreeToHTML(root, frags, {})
        assert html == '|curly2_-0|'
        assert len(frags) == 1
        assert frags[0]['tex'] == r'{{\textnormal{norma tex}}}'

    def test_convertTreeToHTML_macro_noplugin_rectbracket(self):
        body = r'\ldots[a]b '
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        assert root.body == body
        assert len(root.kids) == 2
        assert root.kids[1].type == 'text'

        frags = []
        html = convertTreeToHTML(root, frags, {})
        assert html == '|ldots-0|[a]b '
        assert len(frags) == 1
        assert frags[0]['tex'] == r'\ldots'

        body = r'\hyperref[a]{b}c'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        frags = []
        html = convertTreeToHTML(root, frags, {})
        assert html == '|hyperref-0|c'
        assert len(frags) == 1
        assert frags[0]['tex'] == r'\hyperref[a]{b}'

    def test_convertTreeToHTML_1(self):
        body = 'normal'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        frags = []

        html = convertTreeToHTML(root, frags, {})
        assert html == body
        assert len(frags) == 0

        body = r'$bar$'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        assert root.kids[0].type == '$'

        frags = []
        html = convertTreeToHTML(root, frags, {})
        assert len(frags) == 1
        assert html == '|dollar1_-0|'

        body = r'foo $bar$'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        frags = []
        html = convertTreeToHTML(root, frags, {})
        assert len(frags) == 1
        assert html == 'foo |dollar1_-0|'

        body = r'foo {$bar$}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        frags = []
        html = convertTreeToHTML(root, frags, {})
        assert len(frags) == 1
        assert html == 'foo |dollar1_-0|'

        body = r'foo {{$bar$}}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        frags = []
        html = convertTreeToHTML(root, frags, {})
        assert len(frags) == 1
        assert html == 'foo |curly2_-0|'

        body = r'foo {{$bar$}} \begin{blah}something\end{blah}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        frags = []
        html = convertTreeToHTML(root, frags, {})
        assert len(frags) == 2
        assert html == 'foo |curly2_-0| <div align="center">|blah-1|</div><p>'

    def test_convertTreeToHTML_plugin_env(self):
        def c_itemize(nodes, parent):
            return '<ul>', nodes, '</ul>'

        body = r'\begin{itemize}foo\end{itemize}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list, ['itemize'])
        root = buildTree(body, delim_list)
        frags = []
        html = convertTreeToHTML(root, frags, {'itemize': c_itemize})
        assert len(frags) == 0
        assert html == '<ul>foo</ul>'

        body = r'\begin{itemize}foo $x=1$\end{itemize}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list, ['itemize'])
        root = buildTree(body, delim_list)
        frags = []
        html = convertTreeToHTML(root, frags, {'itemize': c_itemize})
        assert len(frags) == 1
        assert html == '<ul>foo |dollar1_-0|</ul>'

    def test_convertTreeToHTML_plugin_env_bug1(self):
        """
        Bug occurred if a macro for which a plugin existed was nested inside an
        environment, even if was just a {} environment.
        """
        def c_ldots(nodes, parent):
            return '...', nodes

        body = r'{foo\ldots}'
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list, ['ldots'])
        root = buildTree(body, delim_list)

        frags = []
        html = convertTreeToHTML(root, frags, {'ldots': c_ldots})
        assert len(frags) == 0
        assert html == 'foo...'

    def test_convertTreeToHTML_plugin_macro(self):
        def c_ldots(nodes, parent):
            ret = '...', nodes
            return ret

        def c_fbox(nodes, parent):
            ret = 'fbox[', nodes, ']'
            return ret

        body = r'foo\ldots '
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        frags = []
        html = convertTreeToHTML(root, frags, {'ldots': c_ldots})
        assert len(frags) == 0
        assert html == 'foo... '

        body = r'foo \fbox{bar} '
        delim_list = findDelimiters(body)
        delim_list = pruneDelimiters(delim_list)
        root = buildTree(body, delim_list)
        frags = []
        html = convertTreeToHTML(root, frags, {'fbox': c_fbox})
        assert len(frags) == 0
        assert html == 'foo fbox[bar] '

    def test_convertTextToHTML(self):
        body = 'foo'
        out = convertTextToHTML(body)
        assert out == body

        body = r'a \$ b \{ c \} d \%'
        out = convertTextToHTML(body)
        assert out == 'a $ b { c } d %'

        body = r'x<3 and 4>y'
        out = convertTextToHTML(body)
        assert out == r'x&lt;3 and 4&gt;y'

        body = "a ``b'' c"
        out = convertTextToHTML(body)
        assert out == r'a &ldquo;b&rdquo; c'
