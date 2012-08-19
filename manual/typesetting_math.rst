
.. include:: global.rst

.. _typesetting_math:


Typesetting Math in ebooks
============================

The |app| ebook viewer has the ability to display math embedded in ebooks (ePuB
and HTML files). You can typeset the math directly with TeX or MathML or
AsciiMath. The |app| viewer uses the excellent `MathJax
<http://www.mathjax.org>`_ library to do this. This is a brief tutorial on
creating ebooks with math in them that work well with the |app| viewer.

A simple HTML file with mathematics
-------------------------------------

You can write mathematics inline inside a simple HTML file and the |app| viewer
will render it into properly typeset mathematics. In the example below, we use
TeX notation for mathematics. You will see that you can use normal TeX
commands, with the small caveat that ampersands and less than and greater than
signs have to be written as &amp; &lt; and &gt; respectively.

The first step is to tell |app| that this will contains maths. You do this by
adding the following snippet of code to the <head> section of the HTML file::

    <script type="text/x-mathjax-config"></script>

That's it, now you can type mathematics just as you would in a .tex file. For
example, here are Lorentz's equations::

    <h2>The Lorenz Equations</h2>

    <p>
    \begin{align}
    \dot{x} &amp; = \sigma(y-x) \\
    \dot{y} &amp; = \rho x - y - xz \\
    \dot{z} &amp; = -\beta z + xy
    \end{align}
    </p>

This snippet looks like the following screen shot in the |app| viewer.

.. figure:: images/lorentz.png
    :align: center

    :guilabel:`The Lorentz Equations`

The complete HTML file, with more equations and inline mathematics is
reproduced below. You can convert this HTML file to EPUB in |app| to end up
with an ebook you can distribute easily to other people.

.. only:: online

    Here is the generated EPUB file: `mathjax.epub <_static/mathjax.epub>`_.

.. literalinclude:: mathjax.html
    :language: html

More information
-----------------

Since the |app| viewer uses the MathJax library to render mathematics, the best
place to find out more about math in ebooks and get help is the `MathJax
website <http://www.mathjax.org>`_.

