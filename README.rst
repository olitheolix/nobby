======
Nobby
======

Nobby converts a LaTeX file into a single HTML file + SVG images.
Nobby2WP uploads the HTML file + SVG images to a Wordpress server.

The main purpose of these two tools is to only keep LaTeX files under
version control, not an entire Wordpress installation.

Nobby uses SVG images to facilitate seamless scaling of all equations
and text. See `here <https://olitheolix.github.io/nobby/>`_ for a live
demonstration of the converted `demo.tex
<https://github.com/olitheolix/nobby/blob/master/demo/demo.tex>`_ file
looks on a Wordpress site.

If you want to write web articles in LaTeX then Nobby may be for
you. If you are looking for a way to convert your thesis
to HTML then... maybe not, but feel free to try anyway!


More Information
================

Nobby's strategy is to copy plain text verbatim from the LaTeX file to
the HTML file and convert everything else (eg. macros and environments)
into SVG images. Nobby does *not* make any attempt to interpret LaTeX
code. Everything Nobby can and cannot do is a direct consequence of
this strategy.

This strategy is flexible enough to support custom macros
and environments. You can even include figures and tables,
use the `subcaption` package to organise them, and reference them like
in LaTeX. The strategy is *not* flexible enough to reproduce page
layouts (eg. two-column) or fancy page headers.

See documentation for possible gotchas and more information (you may have to
build it first with `make html` in the `doc/` folder).

The documentation also explains the plugin system to alter the HTML
conversion of individual macros and environments. Plugins can, for
instance, convert ``\ldots`` to '...' and ``\section{}`` to the
corresponding ``<h1>`` and ``</h1>`` tags.

It *may* be possible to support bibliographies and table-of-contents. Patches
welcome.


Examples
========

To see all options type

.. code-block:: bash

  >> python nobby.py -h

Typically, you run Nobby like this:

.. code-block:: bash

  >> python nobby.py somefile.tex

or this:

.. code-block:: bash

  >> python nobby.py somefile.tex --scale 1.2

The ``--scale`` argument - wait for it - scales all SVG images. This
is often necessary to match the font size in the SVG images to the
HTML font size.


Installation
============

Nobby relies these external tools:

* Python >= 3.3
* NumPy
* Matplotlib
* pdfinfo
* pdf2svg
* pdfcrop
* pdflatex
* latexmk
* convert (part of ImageMagick)

To run Nobby2WP you will also need the `python-wordpress-xmlrpc` package.


Debian based systems like (K)Ubuntu
-----------------------------------

.. code-block:: bash

   apt install pdf2svg texlive-extra-utils latexmk imagemagick
   pip install python-wordpress-xmlrpc


RedHat / Fedora
---------------

.. code-block:: bash

  yum install pdf2svg texlive texlive-pdfcrop latexmk ImageMagick
  pip install python-wordpress-xmlrpc


Windows and OsX
---------------

No idea, but should be possible as well.


Clone Nobby
--------------

To get Nobby and run the unit tests type this:

.. code-block:: bash

   git clone https://github.com/olitheolix/nobby.git
   py.test


Quickstart
==========

To compile `demo.tex` and view the result in the browser:

.. code-block:: bash

   git clone https://github.com/olitheolix/nobby.git
   python nobby.py demo/demo.tex -w

To publish it via Wordpress edit the demo/.credentials file to specify the
Wordpress URL, username, password, SSH credentials, etc. Make sure you
create the ``wp-img`` path (see comments).

.. code-block:: bash

   cd demo
   python ../nobby2wp.py --verify

If this succeeds then you can upload the post (as a Wordpress 'page')
like this:

.. code-block:: bash

   python ../nobby2wp.py html-demo/demo.html --type page

Login to your Wordpress site and verify that it has a new entry in the
`Pages` tab.


Documentation
=============

To build the documentation with Sphinx:

.. code-block:: bash

   make -C doc/ clean html


Not what you are looking for?
=============================

You may want to try `Quick Latex <http://www.quicklatex.com/>`_ if you
have web publishing in mind. It is an online converter for LaTeX, uses
a similar strategy as Nobby, and comes with a Wordpress plugin.

Another option is
`latex2wp <http://lucatrevisan.wordpress.com/latex-to-wordpress/>`_,
or the related `Lyx2Wordpress <http://physicspages.com/tag/latex2wp/>`_.

For more general LaTeX to HTML converters see
`latex2html <http://www.latex2html.org/>`_,
`PlasTeX <http://plastex.sourceforge.net/>`_, and
`SnuggleTeX <http://www2.ph.ed.ac.uk/snuggletex/documentation/overview-and-features.html>`_.


License
=======

Nobby is licensed under the terms of the GPL v3.
