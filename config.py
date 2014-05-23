# Copyright 2014, Oliver Nagy <olitheolix@gmail.com>
#
# This file is part of Nobby.
#
# Nobby is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Nobby is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Nobby. If not, see <http://www.gnu.org/licenses/>.

import multiprocessing

# Removes build directory when nobby is done.
keep_builddir = False

# If True, then existing fragment images will not be compiled again.
skip_existing_fragments = True

# Maximum size of SVG image (in Bytes) before it will be converted to PNG.
max_svg_size = 200000

# Display all environments that Nobby could not convert.
show_unconverted_envs = True

# Prefix of placeholder strings. The purpose of this prefix is create a tag
# that is unlikely to occur naturally in either the LaTeX document or the
# generated HTML file.
placeholder_prefix = 'nobby'

# Scale all PDF images by this factor (1.0 means no scaling).
pdf_scale = 1.3

# Change the following parameter to align the created image size with the width
# of the HTML page.  The following value will be added to to LaTeX \textwidth
# length in every fragment. The purpose of this parameter is to align the line
# width of the LaTeX document with the line width of the HTML document. For
# equations this is rarely a problem, but other commands that scale their
# content relative to \textwidth it can be A typical example is the
# 'includegraphics' command, eg. '\includegraphics[width=0.5\textwidth]'. The
# absolute image size of the created SVG image now depends on \textwidth.
textwidth_addon = 0

# Number of worker processes to compile fragments.
num_processes = multiprocessing.cpu_count()

# Format of LaTeX fragment placeholders. These will replace the LaTeX code
# portion that will be compiled to an image. Once the image exists, proper
# HTML tags will replace these strings.
ph_format = '{0}-{1:06d}'

# Format of HTML image inclusion tags.
tag_format = '<img src="{}" style="vertical-align: middle;">'

# If True, then the full LaTeX code, including preamble and everything will be
# listed, instead of only the source code fragment.
errtex_showfull = False

# An empty SVG file. This is sometimes necessary when the LaTeX does not
# produce any visible output (eg. \rule{1cm}{0cm} will be invisible).
empty_svg = """
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink" width="0"
     height="0pt" viewBox="0 0 0 0" version="1.1">
</svg>
"""

# Nobby will not print a warning for these environments.
benign_node_types = ['dollar1_', 'dollar2_', 'curly1', 'curly2', 'equation',
                     'align', 'figure', 'tikzpicture', 'comment_']

# Verbosity level.
verbose = False

# If True, Nobby will open the HTML file in the default browser.
launch_browser = False

# Number of LaTeX invocations per file.
num_compile_iter = 1

# Nobby will record all LaTeX counter values right before these environments
# and macros. If you define/use additional environments/macros that alter
# counters, add those environments/macros to the corresponding list.
counter_dump_envs = ['align', 'equation', 'figure', 'table', 'subequations',
                     'eqnarry', 'multiline', 'gather', 'flalign', 'alignat',
                     'lemma', 'theorem', 'example', 'corollary', 'definition']
counter_dump_macros = ['section', 'subsection', 'subsubsection']

# Nobby will track these LaTeX counters. If you specify new theorem like
# environments with '\newtheorem{foo}{Foo} then you must add 'foo' to the
# list. Add all additional counters you want to track to this list.
counter_names = ('section', 'subsection', 'subsubsection',
                 'equation', 'figure', 'table', 'footnote',
                 'lemma', 'theorem', 'example', 'corollary', 'definition')

# Serves as a global variable for the parsed .nobby file. It will be a list of
# named tuples that specify locations in the source code along with a
# corresponding set of LaTeX counter values. The variable is set only once
# after the salted LaTeX file compiled. It is supposed to remain constant
# thereafter.
counter_values = tuple()
