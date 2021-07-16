# .. Copyright (C) 2012-2020 Bryan A. Jones.
#
#   This file is part of the CodeChat System.
#
#   The CodeChat System is free software: you can redistribute it and/or
#   modify it under the terms of the GNU General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   The CodeChat System is distributed in the hope that it will be
#   useful, but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with the CodeChat System.  If not, see
#   <http://www.gnu.org/licenses/>.
#
# *********************************************
# |docname| - Renderers for the CodeChat Server
# *********************************************
# These functions render a document to HTML for a variety of formats.
#
# .. contents:: Table of Contents
#   :local:
#   :depth: 2
#
#
# Imports
# =======
# Library imports
# ---------------
import ast
import asyncio
import codecs
from contextlib import contextmanager
import fnmatch
import io
from pathlib import Path
import shlex
import sys
from tempfile import NamedTemporaryFile
from typing import (
    Any,
    cast,
    Callable,
    Coroutine,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Union,
)

# Third-party imports
# -------------------
from CodeChat.CodeToRest import code_to_rest_string, html_static_path  # type: ignore
from CodeChat.CommentDelimiterInfo import SUPPORTED_GLOBS  # type: ignore
import docutils.core
import docutils.writers.html4css1
import markdown  # type: ignore
import strictyaml


# Local imports
# -------------
# None
#
# Internal renderers
# ==================
# These renderers are invoked via function calls to 3rd party Python libraries.
#
# They all return ``(html, errors)``.
#
# Markdown
# --------
# Convert Markdown to HTML
def _render_markdown(text: str, file_path: str) -> Tuple[str, str]:
    return (
        markdown.markdown(
            text,
            # See https://python-markdown.github.io/extensions/. Enable a few by default.
            extensions=[
                "markdown.extensions.extra",
            ],
        ),
        "",
    )


# reStructuredText (reST)
# -----------------------
# Convert reStructuredText (reST) to HTML.
def _render_ReST(
    text: str, filePath: str, use_codechat: bool = False
) -> Tuple[str, str]:

    errStream = io.StringIO()
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
        "stylesheet_dirs": html_static_path(),
        "stylesheet_path": ["docutils.css"]
        + (["CodeChat.css"] if use_codechat else []),
    }
    htmlString = docutils.core.publish_string(
        bytes(text, encoding="utf-8"),
        writer_name="html",
        settings_overrides=settingsDict,
    )
    errString = errStream.getvalue()
    errStream.close()
    return htmlString, errString


# CodeChat
# --------
# Convert source code to HTML.
def _render_CodeChat(text: str, filePath: str) -> Tuple[str, str]:
    try:
        rest_string = code_to_rest_string(text, filename=filePath)
    except KeyError:
        # Although the file extension may be in the list of supported
        # extensions, CodeChat may not support the lexer chosen by Pygments.
        # For example, a ``.v`` file may be Verilog (supported by CodeChat)
        # or Coq (not supported). In this case, provide an error message.
        return (
            "",
            "{}:: ERROR: this file is not supported by CodeChat.".format(filePath),
        )
    return _render_ReST(rest_string, filePath, True)


# Fake renderers
# --------------
# "Render" (pass through) the provided text.
def _pass_through(text: str, file_path: str) -> Tuple[str, str]:
    return text, ""


# The "error renderer" when a renderer can't be found.
def _error_renderer(text: str, file_path: str) -> Tuple[str, str]:
    return "", "{}:: ERROR: No converter found for this file.".format(file_path)


# External renderers
# ==================
# These renderers run in an external program and are all invoked as a subprocess.
#
# Provide a type alias for the ``co_build`` function.
Co_Build = Callable[[str], Coroutine[Any, Any, None]]


# Single-file
# -----------
# Convert a single file using an external program.
async def _render_external_file(
    text: str,
    file_path: str,
    tool_or_project_path: List[Union[bool, str]],
    co_build: Co_Build,
) -> Tuple[str, str]:
    # Split the provided tool path.
    uses_stdin, uses_stdout, *args_ = tool_or_project_path
    args = cast(List[str], args_)

    # Run from the directory containing the file.
    cwd = Path(file_path).parent

    # Save the text in a temporary file for use with the external tool.
    with _optional_temp_file(not uses_stdin) as input_file, _optional_temp_file(
        not uses_stdout
    ) as output_file:
        if input_file:
            # Write the text to the input file then close it, so that it can be opened on all platforms by the external tool. See `NamedTemporaryFile <https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile>`_.
            input_file.write(text)
            input_file.close()

        if output_file:
            # Close the output file for the same reason.
            output_file.close()

        # Do replacements on the args.
        args = [
            s.format(
                input_file=input_file and input_file.name,
                output_file=output_file and output_file.name,
            )
            for s in args
        ]

        stdout, stderr = await _run_subprocess(
            args, cwd, None if input_file else text, bool(output_file), co_build
        )

        # Gather the output from the file if necessary.
        if output_file:
            with open(output_file.name, "r", encoding="utf-8") as f:
                stdout = f.read()

    return stdout, stderr


# Project
# -------
# Convert an project using an external renderer.
async def _render_external_project(
    text: str, file_path_: str, _tool_or_project_path: str, co_build: Co_Build
) -> Tuple[str, str]:
    # Run from the directory containing the project file.
    tool_or_project_path = Path(_tool_or_project_path)
    project_path = tool_or_project_path.parent
    await co_build(
        "Loading project file {}.\n".format(tool_or_project_path),
    )

    # Read the project configuration.
    try:
        with open(tool_or_project_path, encoding="utf-8") as f:
            data = f.read()
    except Exception as e:
        return "", "{}:: ERROR: Unable to open. {}".format(tool_or_project_path, e)

    if tool_or_project_path.suffix == ".yaml":
        schema = strictyaml.Map(
            {
                strictyaml.Optional("source_path", default="."): strictyaml.Str(),
                "output_path": strictyaml.Str(),
                "args": strictyaml.Str() | strictyaml.Seq(strictyaml.Str()),
                strictyaml.Optional("html_ext", default=".html"): strictyaml.Str(),
            }
        )
        try:
            data_dict = strictyaml.load(data, schema).data
        except strictyaml.YAMLError as e:
            return "", "{}:: ERROR: Unable to parse. {}".format(tool_or_project_path, e)
    else:
        # Parse it and check the format.
        assert tool_or_project_path.suffix == ".json"
        try:
            data_dict = ast.literal_eval(data)
        except Exception as e:
            return "", "{}:: ERROR: Unable to parse. {}".format(tool_or_project_path, e)
        if not isinstance(data_dict, dict):
            return (
                "",
                "{}:: ERROR: Unexpected type; file should contain a dict, but saw a {}".format(
                    tool_or_project_path, type(data_dict)
                ),
            )

    # If we can drop the ``.json`` format, then we can remove the following validation as well; the YAML data is validated by the schema.
    args = data_dict.get("args")
    # Note that we don't check the type of each element of the list (which should be a str).
    if not (isinstance(args, list) or isinstance(args, str)):
        return (
            "",
            "{}:: ERROR: missing args or wrong type; saw {} (type was {}).".format(
                tool_or_project_path, args, type(args)
            ),
        )
    source_path = data_dict.get("source_path", ".")
    if not isinstance(source_path, str):
        return (
            "",
            "{}:: ERROR: missing source_path or wrong type; saw {} (type was {}).".format(
                tool_or_project_path, source_path, type(source_path)
            ),
        )
    output_path = data_dict.get("output_path")
    if not isinstance(output_path, str):
        return (
            "",
            "{}:: ERROR: missing output_path or wrong type; saw {} (type was {}).".format(
                tool_or_project_path, output_path, type(output_path)
            ),
        )
    html_ext = data_dict.get("html_ext", ".html")
    if not isinstance(html_ext, str):
        return (
            "",
            "{}:: ERROR: wrong type for html_ext; saw {} (type was {}).".format(
                file_path_, html_ext, type(html_ext)
            ),
        )

    # Make paths absolute.
    def abs_path(path: Union[str, Path]) -> Path:
        path_ = Path(path)
        if not path_.is_absolute():
            path_ = project_path / path_
        return path_

    source_path = abs_path(source_path)
    output_path = abs_path(output_path)
    file_path = Path(file_path_)

    # Determine first guess at the location of the rendered HTML.
    try:
        base_html_file = output_path / file_path.relative_to(source_path)
    except Exception as e:
        return (
            "",
            "{}:: ERROR: unable to compute path relative to {}. {}".format(
                file_path, source_path, e
            ),
        )

    # Compare dates to see if the rendered file is current
    html_file, error = _checkModificationTime(file_path, base_html_file, html_ext)

    # If not, render and try again.
    if error:
        # Perform replacement on the args.
        def args_format(arg):
            return arg.format(
                project_path=project_path,
                source_path=source_path,
                output_path=output_path,
            )

        args = (
            args_format(args)
            if isinstance(args, str)
            else [args_format(arg) for arg in args]
        )
        # Render.
        stdout, stderr = await _run_subprocess(args, project_path, None, True, co_build)
        html_file, error = _checkModificationTime(file_path, base_html_file, html_ext)
    else:
        stderr = ""

    # Display an error in the main window if one exists.
    if error:
        stderr += error
    return html_file, stderr


# Support
# -------
# OS detection: This follows the `Python recommendations <https://docs.python.org/3/library/sys.html#sys.platform>`_.
is_win = sys.platform == "win32"


# These functions support external renderers.
# If need_temp_file is True, provide a NamedTemporaryFile; otherwise, return a dummy context manager.
def _optional_temp_file(need_temp_file: bool) -> Any:
    return (
        NamedTemporaryFile(mode="w", encoding="utf-8")
        if need_temp_file
        else _dummy_context_manager()
    )


@contextmanager
def _dummy_context_manager() -> Generator:
    yield


# _`_checkModificationTime`: Return False if source_file is newer than output_file; otherwise, return string with an error message.
def _checkModificationTime(
    source_file: Path, base_html_file: Path, html_ext: str
) -> Tuple[str, str]:

    # Look for the resulting HTML.
    possible_html_file = base_html_file.with_suffix(html_ext)
    html_file = (
        possible_html_file
        if possible_html_file.exists()
        else Path(str(base_html_file) + html_ext)
    )

    # Recall that time is measured in seconds since the epoch,
    # so that larger = newer.
    try:
        if html_file.stat().st_mtime > source_file.stat().st_mtime:
            return str(html_file), ""
        else:
            return (
                str(html_file),
                "{}:: ERROR: CodeChat renderer - source file older than the html file {}.".format(
                    source_file, html_file
                ),
            )
    except OSError as e:
        return (
            str(html_file),
            "{}:: ERROR: CodeChat renderer - unable to check modification time of the html file {}: {}.".format(
                source_file, html_file, e
            ),
        )


# Run a subprocess, optionally streaming the stdout.
async def _run_subprocess(
    args: Union[List[str], str],
    cwd: Path,
    input_text: Optional[str],
    stream_stdout: bool,
    co_build: Co_Build,
) -> Tuple[str, str]:
    # If the args were provided a single string, split it since the asyncio subprocess doesn't accept a string (the standard subprocess does).
    if isinstance(args, str):
        args = shlex.split(args, posix=not is_win)

    # Explain what's going on.
    await co_build("{} > {}\n".format(cwd, " ".join(args)))

    # Start the process.
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return (
            "",
            ":: ERROR: CodeChat renderer - when starting render process, unable to find renderer executable '{}'.\n".format(
                args[0] if len(args) > 0 else "<undefined>"
            ),
        )
    except Exception as e:
        return (
            "",
            ":: ERROR: CodeChat renderer - when starting render process, {}.\n".format(
                e
            ),
        )

    # Provide a way to send stdout from the process a line at a time to the web client.
    async def stdout_streamer(stdout_stream: asyncio.StreamReader):
        # Use an `incremental decoder <https://docs.python.org/3/library/codecs.html#codecs.getincrementaldecoder>`_ to decode a stream.
        decoder_ = codecs.getincrementaldecoder("utf-8")(errors="backslashreplace")
        # Wrap than with an incremental decoder for universal newlines. The `docs <https://docs.python.org/3/library/io.html#io.IncrementalNewlineDecoder>`_ are very sparse. From the Visual Studio Code help that pops up (likely from https://github.com/python/cpython/blob/master/Modules/_io/textio.c#L237):
        #
        #   IncrementalNewlineDecoder(decoder: Optional[codecs.IncrementalDecoder], translate: bool, errors: str=...)
        #
        #   Codec used when reading a file in universal newlines mode.
        #   It wraps another incremental decoder, translating \r\n and \r into \n. It also records the types of newlines encountered.  When used with translate=False, it ensures that the newline sequence is returned in one piece. When used with decoder=None, it expects unicode strings as decode input and translates newlines without first invoking an external decoder.
        decoder = io.IncrementalNewlineDecoder(decoder_, True, "")
        while True:
            ret = await stdout_stream.read(80)
            if ret:
                await co_build(decoder.decode(ret))
            else:
                # Tell the decoder the stream is done and collect any last output.
                s = decoder.decode(b"", True)
                if s:
                    await co_build(s)
                break

    # An awaitable sequence to interact with the subprocess.
    aws = [proc.communicate(None if input_text is None else input_text.encode("utf-8"))]

    # If we have an output file, then stream the stdout.
    if stream_stdout:
        assert proc.stdout
        aws.append(stdout_streamer(proc.stdout))
        # Hack: make it look like there's no stdout, so communicate won't use it.
        proc.stdout = None

    # Run the subprocess.
    try:
        (stdout, stderr), *junk = await asyncio.gather(*aws)
    except Exception as e:
        return "", "external command:: ERROR:When running. {}".format(e)

    return (
        stdout and stdout.decode("utf-8", errors="backslashreplace"),
        stderr.decode("utf-8", errors="backslashreplace"),
    )


# Select and invoke a renderer
# ============================
# Build a map of file names/extensions to the converter to use.
#
# TODO:
#
# #.    Read this from a StrictYAML file instead.
# #.    Use Pandoc to offer lots of other format conversions.
GLOB_TO_RENDERER: Dict[
    # glob: The glob which accepts files this renderer can process.
    str,
    Tuple[
        # The `renderer`_.
        Callable,
        # An list of parameters used to invoke the renderer.
        Optional[List[Union[bool, str]]],
    ],
] = {glob: (_render_CodeChat, None) for glob in SUPPORTED_GLOBS}
GLOB_TO_RENDERER.update(
    {
        # Leave (X)HTML unchanged.
        "*.xhtml": (_pass_through, None),
        "*.html": (_pass_through, None),
        "*.htm": (_pass_through, None),
        # Use the integrated Python libraries for these.
        "*.md": (_render_markdown, None),
        "*.rst": (_render_ReST, None),
        # External tools
        #
        # `Textile <https://www.promptworks.com/textile>`_:
        "*.textile": (
            _render_external_file,
            [
                # Does this tool read the input file from stdin?
                True,
                # Does this tool produce the output on stdout?
                True,
                # The remaining elements are the arguments used to invoke the tool.
                "pandoc",
                # Specify the input format https://pandoc.org/MANUAL.html#option--to>`_.
                "--from=textile",
                # `Output to HTML <https://pandoc.org/MANUAL.html#option--from>`_.
                "--to=html",
                # `Produce a complete (standalone) HTML file <https://pandoc.org/MANUAL.html#option--standalone>`_, not a fragment.
                "--standalone",
            ],
        ),
    }
)


# Return the converter for the provided file.
def _select_renderer(
    file_path: str,
) -> Tuple[
    # _`renderer`: a function or coroutine which will perform the render.
    Callable,
    # tool_or_project_path:
    #
    # - The path to the CodeChat System configuration file if this is a project.
    # - A sequence of parameters used to invoke a single-file renderer if one was found.
    # - None if no renderer was found for ``file_path``.
    Union[str, List[Union[bool, str]], None],
    # is_project: True if this is a project; False if not.
    bool,
]:
    # Search for an external builder configuration file.
    for project_path in Path(file_path).parents:
        project_file = project_path / "codechat_config.json"
        if project_file.exists():
            return _render_external_project, str(project_file), True
        project_file = project_path / "codechat_config.yaml"
        if project_file.exists():
            return _render_external_project, str(project_file), True

    # Otherwise, look for a single-file converter.
    for glob, (converter, tool_or_project_path) in GLOB_TO_RENDERER.items():
        if fnmatch.fnmatch(file_path, glob):
            return converter, tool_or_project_path, False
    return _error_renderer, None, False


# Run the appropriate converter for the provided file or return an error.
async def render_file(
    # The text to be converted. If this is a project, the text will be loaded from the disk by the external renderer instead.
    text: str,
    # The path to the file which (mostly -- see ``is_dirty``) contains this text.
    file_path: str,
    # A coroutine that an external renderer should call to stream build output.
    co_build: Co_Build,
    # True if the provided text hasn't been saved to disk.
    is_dirty: bool,
) -> Tuple[
    # was_performed: True if the render was performed. False if this is a project and the source file is dirty; in this case, the render is skipped.
    bool,
    # rendered_file_path: A path to the rendered file.
    #
    # - If this is a project, the rendered file is different from ``file_path``, since it points to the location on disk where the external renderer wrote the HTML. In this case, the ``html`` return value is ``None``, since the HTMl should be read from the disk instead.
    # - Otherwise, it's the same as the ``file_path``, and the resulting rendered HTMl is returned in ``html``.
    str,
    # html: ``None`` for projects, or the resulting HTML otherwise; see the ``rendered_file_path`` return value.
    Optional[str],
    # err_string: A string containing error messages produced by the render.
    str,
]:
    # Determine the renderer for this file/project.
    renderer, tool_or_project_path, is_project = _select_renderer(file_path)

    # Projects require a clean file in order to render.
    if is_project and is_dirty:
        return False, "", None, ""

    if asyncio.iscoroutinefunction(renderer):
        # Coroutines get the queue, so they can report progress during the build.
        html_string_or_file_path, err_string = await renderer(
            text, file_path, tool_or_project_path, co_build
        )
    else:
        assert tool_or_project_path is None
        html_string_or_file_path, err_string = renderer(text, file_path)

    # Update the client's state, now that the rendering is complete.
    if is_project:
        # For projects, the rendered HTML is already on disk; a path to this rendered file is returned.
        return True, html_string_or_file_path, None, err_string
    else:
        # Otherwise, the rendered HTML is returned as a string and can be directly used. Provide a path to the source file which was just rendered.
        return True, file_path, html_string_or_file_path, err_string
