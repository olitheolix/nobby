.. _plugins:

Plugins
*******

Plugins control the conversion of LaTeX- macros and environments to
HTML.

Nobby converts a LaTeX document into a tree. The root node contains
the entire document body. Its children contain non-overlapping
partitions thereof. Children may themselves have children if the
environments are nested (eg. an *itemize* inside an *itemize*, or an
equation inside an *enumerate*, etc).

For instance, Nobby represents the document

.. code-block:: latex

    \rule{1cm}{2cm}
    \begin{itemize}
      \item A
      \item $x=1$
    \end{itemize}
    The end.

as this tree:

.. image:: images/graph_ex1.svg

Note how `\rule` has two children whereas `\item` has none. Since
Nobby does not know how many arguments a macro requires it assumes
that every [] or {} environment immediately after the macro are
arguments. For this reason, do *not* place any text inside curly
braces right after a macro definition unless they are really macro
arguments. For instance, ``\ldots foo`` is fine, but ``\ldots{foo}``
less so. If a plugin for the macro exists then the plugin must
consume the arguments as necessary.

Nobby distinguishes only a few node types, of which only three
matter to plugins: *text*, *macro*, and *env*. Unsurprisingly, *text*
is for normal text, *macro* denotes a macro (its children are the
arguments), and *env* is anything with explicit `\begin` and `\end`
delimiters.

Text nodes make it verbatim into the HTML output, whereas *macro* and
*env* nodes will become SVG images. Unless a plugin exists for them.

Plugins are Python functions which receive a list of *nodes* and a
*parent*. In the previous example *node* argument to the `\rule`
plugin would hold two nodes, whereas for the `\itemize` plugin it
would hold four (first `item` macro, text following that macro,
second `item` macro, text following that macro).

Every plugin must return a list of nodes. For convenience, the list
may also contain strings instead of text nodes which Nobby 
automatically converts to *text* nodes. Nobby will then replace the
original *macro* or *env* node with the list of nodes returned by the
plugin.

This is easier than it may sound, and the example below will
(hopefully) demonstrate it.

.. note::
   To activate a plugin, add it to the ``plugins`` dictionary at the
   end of 'plugins.py'.


Example: ldots
==============

Here is the plugin for the `\ldots` macro.

.. code-block:: python

    def ldots(nodes, parent):
        return '...', nodes

Like every plugin, it receives a list of nodes. This list should be
empty since `\ldots` requires no arguments. If it is not empty then
the LaTeX code passed an argument to `\ldots`.

The plugin only needs to return '...' because this is the HTML
equivalent of the `\ldots` macro. Nevertheless, it is both safe and
proper to return unconsumed nodes.


Example: emph
==============

Here is the plugin for the `\emph` macro.

.. code-block:: python

    def emph(nodes, parent):
        return '<em>', nodes, '</em>'

This macro takes one argument. The argument is usually just text, but
may contain other macros and equations as well. As such, the ``nodes``
argument may be a list of one or more nodes. Fortunately, we need not
concern ourselves with the content of these **nodes** but merely
return the original **nodes** list enclosed in <em> tags. Nobby will
then proceed to expand these nodes. Whatever they expand to (plain
text, an image, or more nodes returned by another plugin) will be
inside the <em> tags.

Example: the LaTeX code 'foo \emph{important} bar' corresponds to
the tree

.. image:: images/graph_ex2.svg

Without our plugin for `\emph`, Nobby would create the LaTeX file
`\begin{document}\emph{important}\end{document}` and compile
it into an SVG image.

In contrast, with our plugin for `\emph` the following will happen:
Our plugins receives the list of **nodes=[text('important')]** and
returns **[<em>, [text('important')], </em>]**. Nobby will then
convert the strings and flatten the list to obtain the new list
**[text('<em>'), text('important'), text('</em>')]**. Afterwards it
replaces the original macro('emph') node with the (flattened) content
of this list, which leads to the following (now flat) tree:

.. image:: images/graph_ex3.svg

In other words, only text nodes remain and they always make it
verbatim into the HTML file. No SVG images are created.


Example: itemize
================

Here is an example for an environment plugin. Nobby does not
distinguish between *macro*- and *env* nodes as far as plugins are
concerned. They have the same call signature, and must return the same
data types.

The HTML equivalent for `itemize` is an unordered list. The HTML tags
are `<ul>` and `</ul>` and they replace `\begin{itemize}` and
`\end{itemize}`, respectively. The following code does exactly that:

.. code-block:: python

    def itemize(nodes, parent):
        return '<ul>', nodes, '</ul>'

Before we get to the likely present `\item` macros inside the
`itemize` environment, here is what happens in the tree. Suppose the
LaTeX code is

.. code-block:: latex

 \begin{itemize}
  \item A
 \end{itemize}

.. image:: images/graph_ex4.svg

The plugin receives **nodes = [macro(item), text(' A')]** and returns
list **['<ul>', macro(item), text( A), '</ul>']**. Nobby will again
replace the strings with proper text nodes to obtain **[text('<ul>'),
macro(item), text(' A'), text('</ul>')]** and substitutes the *env* node
with this list (dropping all children of the original *env*
node):

.. image:: images/graph_ex5.svg

This tree contains only text node (verbatim HTML code) and an `\item`
macro. Since it is just a macro we can write a plugin for it:

.. code-block:: python

    def item(nodes, parent):
        return '<li>', nodes

This works just like the `\ldots` macro. Easy.

.. note::
   Without a plugin for `\item` Nobby would create a document with
   only an `\item` command in it, which `pdflatex` would probably not
   compile.

    
Example: maketitle
==================

The last example concerns the removal of LaTeX environments and
macros. This is sometimes necessary to neutralise LaTeX commands that
make no sense in HTML, eg. `\newpage` or `\noindent`. In this example
we will neutralise the `\maketitle` macro.

.. code-block:: python

    def maketitle(nodes, parent):
        return nodes
    
This macro returns just the unconsumed nodes. The original
macro(maketitle) node is thus replaced with literally nothing.


Example: theorem
================

The AMS package provides way to define theorem environments, for
instance ``\newtheorem{theorem}{Theorem}``. This particular
environment, along with several others are already defined in the
preamble of `demo/demo.tex`. In fact, Nobby *assumes* these are
defined. The conversion will fail otherwise because the corresponding
counters do not exist.

We could write one plugin for each of `theorem`, `lemma`, etc, or we
could write a single plugin that infers the name automatically. The
second option is cleaner and also makes for a good example of the
**parent** parameter. So far, we have not used it. The **parent**
parameter is the parent node of all nodes in the **nodes**
parameter. Yes, you can obtain the very same node with
eg. ``nodes[0].parent``, but that only works if **nodes** is not
empty, which it may be. Nobby therefore supplies the parent
explicitly.

The **parent** is a :func:``NodeTree`` instance. As such it has a
`name` attribute. If the node describes a macro or environment then
this attribute holds the macro/env name, eg 'ldots' (without leading
backslash) or 'itemize' (without \begin and curly braces). If the node
does not describe a macro or environment then the `name` attribute has
a slightly different meaning. This meaning is of no concern to plugin
authors because Nobby invokes plugins only for macro- and environment
nodes.

The following plugin create a theorem environment in HTML. It consists
of the name (eg. 'theorem', 'lemma', etc) in bold font and the actual
body of the theorem environment. To activate the plugin for 'theorem'
and 'lemma' add ``{'theorem': theorem, 'lemma': theorem}`` to the
``plugin`` dictionary at the end of ``plugins.py``.

.. note::
   The theorem plugin and corresponding entries in the ``plugin``
   dictionary already exist because Nobby ships with a default
   implementation that is slightly more sophisticated than this
   example.

.. code-block:: python

    def theorem(nodes, parent):
        # Write the node name in bold. The node name will most likely
        # be something like 'theorem', 'lemma', 'definition', etc.
        ret = '<b>' + parent.name.capitalize() + '</b>: '
    
        # Put the theorem content itself into a blockquote environment.
        return ret + '<i>', nodes, '</i>'
