import os
from typing import Dict, Any, Callable
import logging

logger = logging.getLogger("ctx")

def format_file_content_markdown(file_data: Dict[str, Any], root_path: str,
                                 get_file_content_func: Callable[..., str],
                                 function_patterns: Dict[str, str]) -> str:
    """
    Formats file content for Markdown output.
    :param file_data: Dictionary containing 'path', 'start_line', 'end_line', 'functions'.
    :param root_path: The root directory of the project.
    :param get_file_content_func: The function to call to retrieve file content.
    :param function_patterns: Dictionary of regex patterns for function extraction (passed to get_file_content_func).
    :return: Markdown formatted string.
    """
    path = file_data['path']
    rel_path = os.path.relpath(path, root_path)

    content_raw = get_file_content_func(
        path,
        function_patterns,
        file_data.get('start_line'),
        file_data.get('end_line'),
        file_data.get('functions')
    )

    # Determine language for syntax highlighting
    ext = os.path.splitext(path)[1].lstrip('.')
    lang = ""
    if ext:
        # Map common extensions to language names for Markdown highlighting
        lang_map = {'py': 'python', 'js': 'javascript', 'ts': 'typescript',
                    'md': 'markdown', 'json': 'json', 'yaml': 'yaml', 'yml': 'yaml',
                    'sh': 'bash', 'css': 'css', 'html': 'html', 'xml': 'xml',
                    'go': 'go', 'rb': 'ruby', 'java': 'java', 'c': 'c', 'cpp': 'cpp',
                    'h': 'c', 'hpp': 'cpp', 'rs': 'rust', 'php': 'php', 'swift': 'swift',
                    'kt': 'kotlin', 'scala': 'scala', 'vue': 'vue', 'jsx': 'javascript',
                    'tsx': 'typescript'}
        lang = lang_map.get(ext, ext) # Default to extension if not mapped

    header = f"**[FILE: /{rel_path}]**"
    if file_data.get('start_line'):
        header += f" (Lines {file_data['start_line']}-{file_data.get('end_line', 'end')})"
    elif file_data.get('functions'):
        header += f" (Functions: {', '.join(file_data['functions'])})"

    return f"{header}\n```{lang}\n{content_raw}\n```"

def format_file_content_json(file_data: Dict[str, Any], root_path: str,
                             get_file_content_func: Callable[..., str],
                             function_patterns: Dict[str, str]) -> Dict[str, Any]:
    """
    Formats file content for JSON output.
    :param file_data: Dictionary containing 'path', 'start_line', 'end_line', 'functions'.
    :param root_path: The root directory of the project.
    :param get_file_content_func: The function to call to retrieve file content.
    :param function_patterns: Dictionary of regex patterns for function extraction (passed to get_file_content_func).
    :return: Dictionary for JSON output.
    """
    path = file_data['path']
    rel_path = os.path.relpath(path, root_path)

    content_raw = get_file_content_func(
        path,
        function_patterns,
        file_data.get('start_line'),
        file_data.get('end_line'),
        file_data.get('functions')
    )

    data = {
        'path': f'/{rel_path}',
        'content': content_raw
    }
    if file_data.get('start_line'):
        data['start_line'] = file_data['start_line']
        data['end_line'] = file_data.get('end_line')
    if file_data.get('functions'):
        data['functions'] = file_data['functions']

    return data