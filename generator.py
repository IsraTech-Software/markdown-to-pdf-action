"""
Markdown to PDF Converter
Asynchronous, Stateless, Cloud-Native Implementation.
"""
import asyncio
import base64
import os
import re
import urllib.parse
from abc import ABC, abstractmethod
from typing import List, Pattern, Match, Optional

import aiofiles
import aiohttp
import markdown
from pygments.formatters import HtmlFormatter
from weasyprint import HTML


class DocumentGenerationException(Exception):
    """Domain exception for general document rendering failures."""
    pass


class ResourceFetchException(DocumentGenerationException):
    """Domain exception for failed external network or file I/O operations."""
    pass


class DocumentRenderer(ABC):
    """
    Interface defining the contract for document generation.
    Enforces 'Code to Interfaces, not Implementations'.
    """

    @abstractmethod
    async def render_async(self, input_path: str, output_path: str) -> None:
        """
        Asynchronously converts a document to a target format.
        :param input_path: Path to the source file.
        :param output_path: Path to the destination file.
        :raises DocumentGenerationException: If the rendering process fails.
        """
        pass

    @abstractmethod
    async def initialize_resources(self) -> None:
        """Provisions connection pools and network resources."""
        pass

    @abstractmethod
    async def teardown_resources(self) -> None:
        """Gracefully terminates network resources."""
        pass


class WeasyPrintMarkdownRenderer(DocumentRenderer):
    """Concrete Strategy utilizing WeasyPrint for PDF generation."""

    def __init__(self, css_path: str, logo_path: str):
        """
        Constructor-based Dependency Injection for external assets.
        :param css_path: Path to custom CSS stylesheet.
        :param logo_path: Path to the corporate logo.
        """
        self._css_path: str = css_path
        self._logo_path: str = logo_path
        self._http_client: Optional[aiohttp.ClientSession] = None

    async def initialize_resources(self) -> None:
        """
        {P: _http_client is null} C {Q: Thread-safe connection pool is established}
        """
        connector: aiohttp.TCPConnector = aiohttp.TCPConnector(limit=10)
        self._http_client = aiohttp.ClientSession(connector=connector)

    async def teardown_resources(self) -> None:
        """
        {P: _http_client is active} C {Q: Connections are gracefully closed}
        """
        if self._http_client:
            await self._http_client.close()

    async def render_async(self, input_path: str, output_path: str) -> None:
        """
        {P: input_path exists and points to a valid Markdown file}
        Command: Execute asynchronous reading, html conversion, and PDF rendering.
        {Q: A valid PDF document is written to output_path}
        """
        md_text: str = await self._read_text_async(input_path)
        html_payload: str = await self._build_html_async(md_text)
        await self._write_pdf_async(html_payload, output_path)

    async def _read_text_async(self, file_path: str) -> str:
        """
        {P: file_path is non-null} C {Q: returns UTF-8 decoded string}
        :param file_path: Path to the file.
        :return: File contents as string.
        :raises ResourceFetchException: If the file is missing or unreadable.
        """
        self._validate_path(file_path)
        return await self._execute_file_read(file_path)

    def _validate_path(self, file_path: str) -> None:
        """
        {P: true} C {Q: path exists or exception is thrown}
        """
        if not os.path.exists(file_path):
            raise ResourceFetchException(f"Target path does not exist: {file_path}")

    async def _execute_file_read(self, file_path: str) -> str:
        """
        {P: file_path is validated} C {Q: returns string contents}
        """
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                return await file.read()
        except IOError as error:
            raise ResourceFetchException(f"Failed reading {file_path}") from error

    async def _build_html_async(self, md_text: str) -> str:
        """
        {P: md_text is a valid string} C {Q: returns an assembled HTML document string}
        """
        parsed_body: str = await self._parse_markdown_async(md_text)
        css_styles: str = await self._get_styles_async()
        logo_html: str = await self._get_logo_html_async()
        return self._assemble_html(parsed_body, css_styles, logo_html)

    async def _parse_markdown_async(self, md_text: str) -> str:
        """
        {P: md_text is valid markdown} C {Q: returns parsed HTML body}
        """
        md_text = self._apply_page_breaks(md_text)
        md_text = await self._apply_mathjax_async(md_text)
        return self._convert_to_html(md_text)

    def _apply_page_breaks(self, md_text: str) -> str:
        """
        {P: md_text contains arbitrary characters} C {Q: layout tags are standardized}
        """
        md_text = md_text.replace(r'\newpage', '<div style="page-break-before: always;"></div>')
        return md_text.replace(r'\n', '<br/>')

    async def _apply_mathjax_async(self, md_text: str) -> str:
        """
        {P: md_text contains LaTeX delimiters} C {Q: LaTeX is replaced with base64 images}
        """
        block_regex: Pattern = re.compile(r'(?<!\\)\$\$(.*?)(?<!\\)\$\$', re.DOTALL)
        inline_regex: Pattern = re.compile(r'(?<!\\)\$(?!\s)([^$\n]+?)(?<!\s)(?<!\\)\$')
        
        md_text = await self._replace_async(block_regex, md_text, is_block=True)
        return await self._replace_async(inline_regex, md_text, is_block=False)

    async def _replace_async(self, pattern: Pattern, text: str, is_block: bool) -> str:
        """
        {P: pattern is compiled regex} C {Q: all regex matches are replaced concurrently}
        Loop Invariant: Remaining unreplaced matches decrease by the length of the matches array.
        """
        matches: List[Match] = list(pattern.finditer(text))
        if not matches:
            return text

        tasks = [self._fetch_math_base64_async(m.group(1)) for m in matches]
        base64_images: List[str] = await asyncio.gather(*tasks)

        return self._stitch_replacements(text, matches, base64_images, is_block)

    def _stitch_replacements(self, text: str, matches: List[Match], images: List[str], is_block: bool) -> str:
        """
        {P: matches and images lists are of equal length} C {Q: string is fully replaced}
        """
        offset: int = 0
        for match, b64_img in zip(matches, images):
            html_tag = self._format_math_tag(b64_img, is_block)
            start = match.start() + offset
            end = match.end() + offset
            text = text[:start] + html_tag + text[end:]
            offset += len(html_tag) - (end - start)
        return text

    def _format_math_tag(self, b64_img: str, is_block: bool) -> str:
        """
        {P: b64_img is valid image data} C {Q: returns valid HTML span/img tag}
        """
        if is_block:
            return f'<span style="display:block; text-align:center; margin: 15px 0;"><img src="{b64_img}" style="height: 1em; max-width: 100%;" alt="Block Math" /></span>'
        return f'<img style="vertical-align: text-bottom; height: 1em; margin: 0 2px;" src="{b64_img}" alt="Inline Math" />'

    async def _fetch_math_base64_async(self, math_str: str) -> str:
        """
        {P: math_str is a valid LaTeX string} C {Q: returns a base64 encoded data URI}
        """
        query: str = r'\dpi{300} \bg_white ' + math_str.strip()
        url: str = "https://latex.codecogs.com/png.latex?" + urllib.parse.quote(query)
        return await self._execute_network_request(url)

    async def _execute_network_request(self, url: str) -> str:
        """
        {P: URL is valid} C {Q: Network response is encoded or empty string on failure}
        """
        try:
            async with self._http_client.get(url) as response:
                img_data = await response.read()
                b64_str = base64.b64encode(img_data).decode('utf-8')
                return f"data:image/png;base64,{b64_str}"
        except aiohttp.ClientError:
            return ""

    def _convert_to_html(self, md_text: str) -> str:
        """
        {P: md_text is processed markdown} C {Q: returns strict HTML rendering}
        """
        extensions: List[str] = ['fenced_code', 'codehilite', 'tables', 'sane_lists', 'attr_list']
        return markdown.markdown(md_text, extensions=extensions)

    async def _get_styles_async(self) -> str:
        """
        {P: True} C {Q: returns combined CSS string}
        """
        pygments_css: str = HtmlFormatter(style='default').get_style_defs('.codehilite')
        custom_css: str = ""
        
        if self._css_path and os.path.exists(self._css_path):
            custom_css = await self._execute_file_read(self._css_path)
            
        return f"{pygments_css}\n{custom_css}"

    async def _get_logo_html_async(self) -> str:
        """
        {P: True} C {Q: returns logo HTML tag or empty string}
        """
        if not self._logo_path or not os.path.exists(self._logo_path):
            return ""
        return await self._execute_logo_read()

    async def _execute_logo_read(self) -> str:
        """
        {P: Logo path exists} C {Q: Logo is read and encoded}
        """
        try:
            async with aiofiles.open(self._logo_path, "rb") as img_file:
                img_data = await img_file.read()
                b64_str = base64.b64encode(img_data).decode('utf-8')
                return f'<img class="logo-top-right" src="data:image/png;base64,{b64_str}" alt="Logo" />'
        except IOError:
            return ""

    def _assemble_html(self, body: str, css: str, logo: str) -> str:
        """
        {P: all components are valid strings} C {Q: returns formatted HTML wrapper}
        """
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <style>{css}</style>
        </head>
        <body>
            {logo}
            {body}
        </body>
        </html>
        """

    async def _write_pdf_async(self, html_payload: str, output_path: str) -> None:
        """
        Executes CPU-bound WeasyPrint generation on a separate thread.
        {P: html_payload is complete} C {Q: File is flushed to disk}
        """
        def _render_sync():
            HTML(string=html_payload).write_pdf(output_path)
            
        try:
            await asyncio.to_thread(_render_sync)
        except Exception as e:
            raise DocumentGenerationException("WeasyPrint rendering failed.") from e


async def main() -> None:
    """Entrypoint handling argument parsing and pipeline instantiation."""
    import argparse
    parser = argparse.ArgumentParser(description="Async Markdown to PDF CI Pipeline.")
    parser.add_argument('-i', '--input', required=True, help="Input Markdown")
    parser.add_argument('-o', '--output', required=True, help="Output PDF")
    parser.add_argument('-l', '--logo', required=False, default="", help="Logo Image")
    parser.add_argument('-s', '--css', required=False, default="", help="CSS File")
    args = parser.parse_args()

    renderer: DocumentRenderer = WeasyPrintMarkdownRenderer(args.css, args.logo)
    await renderer.initialize_resources()
    try:
        await renderer.render_async(args.input, args.output)
    finally:
        await renderer.teardown_resources()


if __name__ == "__main__":
    asyncio.run(main())
