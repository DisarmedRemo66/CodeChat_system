# .. Copyright (C) 2012-2020 Bryan A. Jones.
#
#    This file is part of the CodeChat plugin.
#
#    The CodeChat plugin is free software: you can redistribute it and/or
#    modify it under the terms of the GNU General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    The CodeChat plugin is distributed in the hope that it will be
#    useful, but WITHOUT ANY WARRANTY; without even the implied warranty
#    of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with the CodeChat plugin.  If not, see
#    <http://www.gnu.org/licenses/>.
#
# *********************************************
# |docname| - Renderers for the CodeChat server
# *********************************************
# These functions convert from a text to HTML for a variety of formats.

# Imports
# =======
# Library imports
# ---------------
import os.path
import io
import fnmatch

# Third-party imports
# -------------------
import markdown
import docutils.core
import docutils.writers.html4css1
from CodeChat.CodeToRest import code_to_html_string
from CodeChat.CommentDelimiterInfo import SUPPORTED_GLOBS

# Local imports
# -------------
# None.


# Functions and classes
# =====================
# A handy Markdown extension.
class _StrikeThroughExtension(markdown.Extension):
    DEL_RE = r"(~~)(.*?)~~"

    def extendMarkdown(self, md, md_globals):
        # Create the del pattern
        delTag = markdown.inlinepatterns.SimpleTagPattern(self.DEL_RE, "del")
        # Insert del pattern into markdown parser
        md.inlinePatterns.add("del", delTag, ">not_strong")


# Convert Markdown to HTML
def _convertMarkdown(text, filePath):

    return (
        markdown.markdown(
            text,
            extensions=[
                "markdown.extensions.fenced_code",
                "markdown.extensions.nl2br",
                "markdown.extensions.tables",
                _StrikeThroughExtension(),
            ],
        ),
        "",
    )


# Convert reStructuredText (reST) to HTML.
def _convertReST(text, filePath):
    errStream = io.StringIO()
    docutilsHtmlWriterPath = os.path.abspath(
        os.path.dirname(docutils.writers.html4css1.__file__)
    )
    settingsDict = {
        # Make sure to use Unicode everywhere. This name comes from
        # ``docutils.core.publish_string`` version 0.12, lines 392 and following.
        "output_encoding": "unicode",
        # While ``unicode`` **should** work for ``input_encoding``, it doesn't if
        # there's an ``.. include`` directive, since this encoding gets passed to
        # ``docutils.io.FileInput.__init__``, in which line 236 of version 0.12
        # tries to pass the ``unicode`` encoding to ``open``, producing:
        #
        # .. code:: python3
        #    :number-lines:
        #
        #    File "...\python-3.4.4\lib\site-packages\docutils\io.py", line 236, in __init__
        #      self.source = open(source_path, mode, **kwargs)
        #    LookupError: unknown encoding: unicode
        #
        # So, use UTF-8 and encode the string first. Ugh.
        "input_encoding": "utf-8",
        # Don't stop processing, no matter what.
        "halt_level": 5,
        # Capture errors to a string and return it.
        "warning_stream": errStream,
        # On some Windows PC, docutils will complain that it can't find its
        # template or stylesheet. On other Windows PCs with the same setup, it
        # works fine. ??? So, specify a path to both here.
        "template": (
            os.path.join(
                docutilsHtmlWriterPath,
                docutils.writers.html4css1.Writer.default_template,
            )
        ),
        "stylesheet_dirs": (
            docutilsHtmlWriterPath,
            os.path.join(
                os.path.abspath(os.path.dirname(os.path.realpath(__file__))),
                "rst_templates",
            ),
        ),
        "stylesheet_path": "default.css",
    }
    htmlString = docutils.core.publish_string(
        bytes(text, encoding="utf-8"),
        writer_name="html",
        settings_overrides=settingsDict,
    )
    errString = errStream.getvalue()
    errStream.close()
    return htmlString, errString


# Convert source code to HTML.
def _convertCodeChat(text, filePath):
    # Use StringIO to pass CodeChat compilation information back to
    # the client.
    errStream = io.StringIO()
    try:
        htmlString = code_to_html_string(text, errStream, filename=filePath)
    except KeyError:
        # Although the file extension may be in the list of supported
        # extensions, CodeChat may not support the lexer chosen by Pygments.
        # For example, a ``.v`` file may be Verilog (supported by CodeChat)
        # or Coq (not supported). In this case, provide an error messsage
        errStream.write(
            "{}:ERROR: this file is not supported by CodeChat.".format(filePath)
        )
        htmlString = ""
    errString = errStream.getvalue()
    errStream.close()
    return htmlString, errString


# "Convert" (pass through) HTML.
def pass_through(text, file_path):
    return text, ""


# Build a map of file names/extensions to the converter to use.
GLOB_TO_CONVERTER = {glob: _convertCodeChat for glob in SUPPORTED_GLOBS}
GLOB_TO_CONVERTER.update(
    {
        # Leave HTML unchanged.
        "*.html": pass_through,
        "*.htm": pass_through,
        "*.md": _convertMarkdown,
        "*.rst": _convertReST,
    }
)


# Run the appropriate converter for the provided file or return an error.
def convert_file(text, file_path):
    # TODO: sphinx.
    for glob, converter in GLOB_TO_CONVERTER.items():
        if fnmatch.fnmatch(file_path, glob):
            return converter(text, file_path)
    return "", "{}:ERROR: no converter found for this file.".format(file_path)