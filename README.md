# LLM Context Builder: Focused Project Context for Large Language Models

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A powerful Python package designed to intelligently select, format, and present relevant project files and directory structure as context for Large Language Models (LLMs). Avoid token limits, reduce noise, and get more accurate, actionable responses from your AI assistant.

---

### 🌟 Why Use This?

Working with LLMs for code-related tasks is incredible, but they often struggle with:

1.  **Token Limits:** Sending an entire codebase is impossible and wasteful.
2.  **Information Overload:** Even if possible, too much irrelevant code confuses the model.
3.  **Lack of Structure:** Raw file dumps lack the directory context a human developer would have.

**LLM Context Builder** solves these problems by allowing you to:
*   **Precisely select** the files, folders, or specific line ranges you want to include.
*   **Automatically ignore** irrelevant files (like `node_modules` or build artifacts) using powerful ignore rules (including `.gitignore`).
*   **Provide a clear project overview** with an automatically generated directory tree.
*   **Format output** in easily parsable Markdown or JSON.

This results in **more focused, relevant, and accurate responses** from your LLM, helping you code faster and more effectively.

---

### 🚀 Getting Started

1.  **Installation:**
    Install `ctx` directly from PyPI:
    ```bash
    pip install ctx
    ```
    If you plan to use [Context Profiles](#7-pre-defined-context-profiles), install with the `yaml` extra:
    ```bash
    pip install "ctx[yaml]"
    ```
    Alternatively, if cloning the repository for development:
    ```bash
    git clone https://github.com/your-username/llm-context-builder.git
    cd llm-context-builder
    # Install with poetry (recommended for development)
    poetry install --with dev
    ```

2.  **Basic Usage:**
    Once installed, you can use the `ctx` command directly from your terminal in any project directory:
    ```bash
    ctx
    ```
    This will generate `prompt_input_files.md` and `prompt_input_files.json` containing only the directory tree of your project, up to a default depth of 3.

---

### 📖 Table of Contents

- [LLM Context Builder: Focused Project Context for Large Language Models](#llm-context-builder-focused-project-context-for-large-language-models)
    - [🌟 Why Use This?](#-why-use-this)
    - [🚀 Getting Started](#-getting-started)
    - [📖 Table of Contents](#-table-of-contents)
    - [✨ Key Features \& Usage Examples](#-key-features--usage-examples)
      - [1. Basic Usage: Include Directory Tree](#1-basic-usage-include-directory-tree)
      - [2. Including Specific Files \& Folders](#2-including-specific-files--folders)
      - [3. Ignoring Files \& Folders](#3-ignoring-files--folders)
      - [4. Targeting Specific Line Ranges](#4-targeting-specific-line-ranges)
      - [5. Using Glob Patterns for Flexible Selection](#5-using-glob-patterns-for-flexible-selection)
      - [6. Passing Arguments from a File](#6-passing-arguments-from-a-file)
      - [7. Pre-defined Context Profiles](#7-pre-defined-context-profiles)
      - [8. Output Formats (Markdown \& JSON)](#8-output-formats-markdown--json)
      - [9. Dry Run Mode](#9-dry-run-mode)
    - [⚙️ Configuration](#️-configuration)
    - [🤝 Contributing](#-contributing)
    - [📄 License](#-license)

---

### ✨ Key Features & Usage Examples

The tool outputs its results into `prompt_input_files.md` (Markdown) and `prompt_input_files.json` (JSON) by default, based on the `OUTPUT_FORMATS` configuration.

#### 1. Basic Usage: Include Directory Tree

The simplest way to get context is just to include your project's directory structure. This gives the LLM a high-level overview of your project's layout, which is often very helpful.

```bash
ctx
```
This will generate `prompt_input_files.md` and `prompt_input_files.json` containing only the directory tree of your project, up to a default depth of 3.

#### 2. Including Specific Files & Folders

The most common use case is to provide the content of a few specific files or all files within a specific folder.

*   **Include a single file:**
    ```bash
    ctx src/main.py
    ```
*   **Include multiple files:**
    ```bash
    ctx src/utils.js README.md
    ```
*   **Include all files within a folder (recursively, up to `SEARCH_MAX_DEPTH`):**
    ```bash
    ctx config/
    ```
*   **Combine files and folders:**
    ```bash
    ctx tests/backend/ src/data_models.py
    ```

#### 3. Ignoring Files & Folders

Crucial for large projects! The tool uses a robust ignore system to ensure you don't send irrelevant or sensitive files to the LLM.

*   **Automatic Gitignore:** By default, the script respects your project's `.gitignore` file.
*   **Built-in Ignores:** Common build artifacts, temporary files, and environment directories (`node_modules`, `__pycache__`, `.venv`, `.git`, `.DS_Store`, etc.) are ignored automatically.
*   **Additional Ignore Files:** The script also looks for other common ignore files like `.dockerignore`, `.npmignore`, and `.eslintignore` defined in `ADDITIONAL_IGNORE_FILENAMES`.
*   **Script-Specific Ignores:** You can create a file named `prompt_builder_ignore.txt` in your project's root directory. Any patterns listed here will *always* be ignored, regardless of your project's `.gitignore`. This is useful for ignoring the tool's own output files or specific local configurations you never want to share.

    Example `prompt_builder_ignore.txt`:
    ```
    # Ignore the script's own output
    prompt_input_files.md
    prompt_input_files.json
    # Never include this local config
    .env.local
    # Ignore a specific test data folder
    test_data/temp_files/
    ```

#### 4. Targeting Specific Line Ranges

For very precise context, you can include one or more specific ranges of lines from a file. This is perfect for focusing on a few key sections of code for debugging or refactoring. The output will clearly mark the included line ranges and indicate where content has been omitted.

*   **Syntax:** `filepath:start1,end1:start2,end2...` (lines are 1-indexed and inclusive).
*   **Example (Single Range):**
    ```bash
    ctx 'src/api/user_routes.py:100,150'
    ```
    This will include lines 100 through 150 from `src/api/user_routes.py`.

*   **Example (Multiple Ranges):**
    ```bash
    ctx 'src/data_processor.py:20,45:200,215'
    ```
    This will include lines 20-45 and 200-215 from the same file, with a comment indicating the omitted lines in between.

#### 5. Using Glob Patterns for Flexible Selection

Glob patterns provide a powerful way to select multiple files based on wildcards.

*   **Syntax:** Standard Unix-style glob patterns (e.g., `*.py`, `src/**/*.js`). Remember to quote patterns to prevent shell expansion.
*   **Example:**
    *   **All Python files:**
        ```bash
        ctx '*.py'
        ```
    *   **All JavaScript or TypeScript files within `src/` and its subdirectories:**
        ```bash
        ctx 'src/**/*.{js,ts}' # (Note: Shell might expand {js,ts}, quote carefully or run in a compatible shell)
        # Safer alternative for cross-platform (multiple arguments):
        ctx 'src/**/*.js' 'src/**/*.ts'
        ```
    *   **All Markdown files in the root or `docs/` folder:**
        ```bash
        ctx '*.md' 'docs/*.md'
        ```

#### 6. Passing Arguments from a File

For very long or complex `ctx` commands, or for commands you use frequently, you can store your queries and flags in a text file and pass that file to `ctx`. This helps keep your terminal commands clean and makes them easily repeatable.

*   **Syntax:** `ctx @filename`
*   **How it works:** `ctx` will read each line from the specified file as if it were a separate command-line argument. Lines starting with `#` are treated as comments and ignored.

*   **Example `my_queries.txt`:**
    ```
    # This is a comment, it will be ignored
    src/main.py
    tests/unit/test_config.py:10,25:50,60
    '*.md'
    docs/api/
    --profile backend_dev
    ```
*   **Usage:**
    ```bash
    ctx @my_queries.txt
    ```
    This command would be equivalent to running:
    ```bash
    ctx src/main.py 'tests/unit/test_config.py:10,25:50,60' '*.md' docs/api/ --profile backend_dev
    ```

#### 7. Pre-defined Context Profiles

For common tasks, you can define **profiles** in an external `prompt_profiles.yaml` file. A profile can include a set of queries and override default configuration settings.

1.  **Create `prompt_profiles.yaml`** in your project's root directory:
    ```yaml
    # prompt_profiles.yaml
    profiles:
      frontend:
        queries:
          - 'src/frontend/**/*.js'
          - 'src/frontend/**/*.ts'
          - 'package.json'
        # Override default ignore patterns for this profile
        substring_ignore_patterns:
          - 'node_modules'
          - 'dist'
        # Override search depth for this profile
        search_max_depth: 7

      backend_api:
        queries:
          - 'src/server/**/*.py'
          - 'requirements.txt'
        # Adjust tree depth for backend context
        tree_max_depth: 4

      refactor_task:
        queries:
          # Focus on specific parts of these files for a refactor
          - 'src/data/processor.py:10,45:100,120'
          - 'src/utils/helpers.py:1,30'
          - 'tests/test_processor.py'
    ```

2.  **Use a profile:**
    ```bash
    ctx --profile backend_api
    ctx --profile refactor_task
    ```
    You can also combine profiles with additional ad-hoc queries:
    ```bash
    ctx --profile frontend 'public/index.html'
    ```

#### 8. Output Formats (Markdown & JSON)

The tool generates two output files by default (`prompt_input_files.md` and `prompt_input_files.json`) to give you flexibility depending on what your LLM prefers or how you want to review the context.

*   **Markdown (`.md`):** Human-readable, includes directory tree, and uses Markdown code blocks with syntax highlighting hints for file contents. Great for reviewing the context yourself before sending it, or for models that prefer structured text.
*   **JSON (`.json`):** Machine-readable structured data. Contains the directory tree as a string and an array of file objects, each with path, content, and any line/function details. Ideal for programmatic use or models that perform better with structured JSON input.

You can configure which formats are generated in the `CONFIG` dictionary (or via a profile).

#### 9. Dry Run Mode

Test your queries and configurations without writing any files. The full output will be printed directly to your console.

```bash
ctx --dry-run 'src/config.py' '*.md'
```

---

### ⚙️ Configuration

The tool's behavior can be customized by modifying the `DEFAULT_CONFIG` dictionary within `ctx/config.py` (for source changes) or overridden by values defined in your `prompt_profiles.yaml`.

Key configurable options include:

*   `ROOT`: The base directory for your project (defaults to `.` - current directory).
*   `OUTPUT_FILE_BASE_NAME`: Base name for output files (e.g., `prompt_input_files`).
*   `OUTPUT_FORMATS`: List of desired output formats (`markdown`, `json`).
*   `TREE_MAX_DEPTH`: Maximum recursion depth for the directory tree view.
*   `SEARCH_MAX_DEPTH`: Maximum recursion depth for file content search.
*   `MAX_MATCHES_PER_QUERY`: Max number of files a single query can return before an error is raised (prevents accidental large inclusions).
*   `EXPLICIT_IGNORE_NAMES`: A set of exact file/folder names or relative paths to always ignore.
*   `SUBSTRING_IGNORE_PATTERNS`: A list of substrings that, if found anywhere in a file's relative path, will cause it to be ignored.
*   `USE_GITIGNORE`: Boolean to enable/disable `.gitignore` integration.
*   `GITIGNORE_PATH`: Relative path to your main `.gitignore` file.
*   `ADDITIONAL_IGNORE_FILENAMES`: List of other ignore files (e.g., `.dockerignore`) to load.
*   `SCRIPT_DEFAULT_IGNORE_FILE`: Name of the script-specific ignore file (defaults to `prompt_builder_ignore.txt`).
*   `PROFILE_CONFIG_FILE`: Path to your external YAML profile configuration.

---

### 🤝 Contributing

Contributions are welcome! If you have ideas for new features, improvements, or bug fixes, please open an issue or submit a pull request.

Areas for future improvement include:
*   **Git Integration:** Automatically include files based on Git status (e.g., staged, modified).
*   **Code-aware Extraction:** Use AST (Abstract Syntax Tree) parsing to extract specific functions, classes, or methods from code files.
*   **Advanced Ignore Logic:** More robust `.gitignore` parsing, including support for negation patterns (`!`).
*   **Interactive Mode:** A CLI mode for interactively selecting files and folders to include in the context.

---

### 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.