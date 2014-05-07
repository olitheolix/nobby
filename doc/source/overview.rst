========
Overview
========

Nobby converts LaTeX documents into an HTML file + SVG images.

Its strategy, in a nutshell, is to divvy up the LaTeX document into
two types of fragments: text- and non-text (eg. equations, figures,
macros, etc) fragments. Nobby then compiles the non-text fragments
to SVG images and stitches them together with the text fragments to
create the HTML file.

This strategy is not new. The `Preview LaTeX
<http://www.gnu.org/software/auctex/preview-latex.html>`_
package for Emacs and `Quick LaTeX <http://www.quicklatex.com/>`_, an
online converter, pursue similar strategies. Where Nobby differs from
these tools is that it creates explicit HTML and SVG files that can be
directly viewed in the browser (launch Nobby with the ``--wb`` option
to save you the effort).


Who is it for
=============

Nobby is for people who want to write articles in LaTeX but publish
them on the web.

In conjunction with ``nobby2wp`` script, it is also for people who
want to write their Wordpress posts in LaTeX and upload/update them via
the command line.

Nobby is *not* for people who want to convert their PhD thesis to HTML
and expect it to "just work" (but feel free to try).

Rules of thumb: the conversion will likely succeed if you

* use ``\documentclass{article}``,
* refrain from (re)defining macros and LaTeX variables in the document
  body (preamble is fine),
* abstain from layout altering packages,
* use common sense.

The documents may contain anything `pdflatex` can compile, including
equations and figures. Floating environments will not float as such on
the web page, but appear exactly where they are defined in the LaTeX
body.


Gotchas
=======

As mentioned already, Nobby compiles every LaTeX fragment that does
not translate to plain text into SVG images. These fragments
constitute individual LaTeX documents. They do not know of each others
existence. The limitation of this approach should be mostly self evident,
but some of those are worth pointing out explicitly:

* Enumerations in eg. `equation` environments will always start at (1)
  in every new fragment.
* Fragments can not cross reference each other.
* Use ``\textbackslash{foo}`` instead of ``\textbackslash foo`` to
  avoid any whitespace between the backslash and the next characters.
* Do not use `modal commands
  <http://www.tex.ac.uk/cgi-bin/texfaq2html?label=2letterfontcmd>`_ 
* ``\input`` works, but will convert the included code into an image.
* Do not specify a font size in the ``documentclass`` (for font sizes
  other than 10pt this sometimes causes problems for unknown reasons).
* Do not use ``\verb``! Use ``\texttt{}`` instead if all you want
  is the typewriter font. See `here 
  <http://tex.stackexchange.com/questions/2790/when-should-one-use-verb-and-when-texttt>`_
  for a discussion on the use of ``\verb``.

Other notably unsupported features are:

* Bibliography
* Footnote
* Fancy page styles
* commands that make no sense in HTML (eg. \parskip, \newpage, etc.)


Labels and Cross references
===========================

Nobby *attempts* to convert ``\label`` macros to HTML anchors. If the
label appears inside a fragment the corresponding HTML anchor wraps
the entire SVG image.

Nobby does *not* convert ``\ref`` macros, only ``\hyperref``. For
instance, use ``see \hyperref[eqn]{Eq.}`` instead of ``see
Eq.\ref{eqn}``. Once again, this produces the same result in LaTeX,
but provides the necessary text for the HTML link.


Plugins
=======

Nobby does not interpret LaTeX code (with few exceptions like
``\label`` and ``\\``). It has no concept of what eg. ``\ldots``
means. Instead it will create a LaTeX file with only the ``\ldots``
command in it (plus the full preamble), compile it to PDF with
`pdflatex`, convert the result to SVG, and include that image from the
HTML file.

This strategy makes sense for some macros/environments like
'equation', but not so much for others like ``\ldots``, which merely
produces three dots. To compound this problem Nobby supports :ref:`plugins` to
customise the HTML conversion of any macro or environment. Nobby
already includes plugins for environments like ``itemize`` and
``enumerate``, as well as macros like ``\ldots`` and ``\section``,
``\texttt``, ``\textbf``.
