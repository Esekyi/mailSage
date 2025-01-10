import re
from pathlib import Path
from typing import Dict, List, Optional
import yaml
import markdown
from flask import current_app
from app.extensions import redis_client
from app.utils.logging import logger
import json
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, TextLexer


class DocsLoader:
    """Service for loading and managing GitHub-flavored markdown documentation."""

    def __init__(self, docs_dir: str = 'docs'):
        self.docs_dir = docs_dir
        self.docs_cache = {}
        self.md = markdown.Markdown(
            extensions=[
                'meta',
                'fenced_code',
                'tables',
                'toc',
                'mdx_gh_links',     # GitHub-style links
                'mdx_linkify',      # Auto-link URLs
                'codehilite',       # Syntax highlighting
                'nl2br',            # GitHub-style line breaks
                'sane_lists',       # GitHub-style lists
                'pymdownx.tasklist',  # GitHub-style task lists
                'pymdownx.superfences',  # Better fenced code blocks
                'pymdownx.betterem',     # Better emphasis handling
                'attr_list',
            ],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight',
                    'use_pygments': True,
                    'guess_lang': False,
                    'noclasses': True,
                    'style': 'monokai'  # Changed from 'github' to built-in style
                },
                'pymdownx.tasklist': {
                    'custom_checkbox': True
                },
                'pymdownx.superfences': {
                    'disable_indented_code_blocks': True,
                    'preserve_tabs': True,
                    'css_class': 'highlight'
                }
            }
        )

        # Pre-generate formatter for code highlighting
        self.formatter = HtmlFormatter(
            cssclass='highlight',
            noclasses=True
        )

    def _highlight_code(self, code: str, language: str) -> str:
        """Highlight code with inline styles for reliable rendering."""
        try:
            lexer = get_lexer_by_name(language)
        except ValueError:
            lexer = TextLexer()

        return highlight(code, lexer, self.formatter)

    def _process_content(self, content: str) -> str:
        """Pre-process markdown content."""
        # Fix Windows line endings
        content = content.replace('\r\n', '\n')

        # Fix heading IDs - convert {#id} syntax to markdown-compatible format
        content = re.sub(
            r'^(#+)\s*(.*?)\s*\{#([^}]+)\}',
            r'\1 \2 {: #\3}',
            content,
            flags=re.MULTILINE
        )

        # Fix heading lines - ensure space after #
        content = re.sub(
            r'^(#+)\s*(.*?)\s*$',
            r'\1 \2',
            content,
            flags=re.MULTILINE
        )

        # Fix code blocks - ensure proper spacing and language tags
        def fix_code_block(match):
            lang = match.group(1) or ''
            code = match.group(2).strip()
            return f"\n```{lang}\n{code}\n```\n"

        content = re.sub(
            r'```(.*?)\n(.*?)```',
            fix_code_block,
            content,
            flags=re.DOTALL
        )

        # Ensure proper table formatting
        content = re.sub(
            r'(\|[^\n]+\|)\n(?!\|)',
            r'\1\n\n',
            content
        )

        # Ensure code blocks have proper spacing
        content = re.sub(
            r'```(\w+)?',
            r'\n```\1',
            content
        )

        return content

    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        text = re.sub(r'[^\w\s-]', '', text.lower())
        return re.sub(r'[-\s]+', '-', text).strip('-')

    def _add_css_classes(self, html_content: str) -> str:
        """Add CSS classes and structure to HTML."""
        # Add wrapper div
        html_content = f'<div class="markdown-body">{html_content}</div>'

        # fix code blocks
        html_content = re.sub(
            r'<pre><code class="([^"]+)">',
            r'<pre class="highlight"><code class="language-\1">',
            html_content
        )

        # Style tables
        html_content = html_content.replace(
            '<table>',
            '<div class="table-wrapper"><table class="markdown-table">'
        ).replace('</table>', '</table></div>')

        # Style headings with proper IDs
        for i in range(1, 7):
            html_content = re.sub(
                f'<h{i}>([^<]+)</h{i}>',
                f'<h{
                    i} id="\\1" class="heading">\\1<a href="#\\1" class="anchor-link">#</a></h{i}>',
                html_content,
                flags=re.IGNORECASE
            )

        return html_content

    def _make_id(self, text: str) -> str:
        """Create URL-friendly ID from text."""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Convert to lowercase and replace spaces/special chars
        return re.sub(r'[^a-z0-9-]', '', text.lower().replace(' ', '-'))

    def load_docs(self) -> Dict[str, Dict]:
        """Load all markdown documents from the docs directory."""
        docs = {}
        docs_path = Path(current_app.root_path).parent / self.docs_dir

        for file_path in docs_path.rglob('*.md'):
            try:
                relative_path = file_path.relative_to(docs_path)
                slug = str(relative_path.with_suffix('')).replace('\\', '/')

                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse frontmatter and content
                front_matter, content = self._parse_frontmatter(content)

                # Process content
                content = self._process_content(content)

                # Convert markdown to HTML
                self.md.reset()
                html_content = self.md.convert(content)
                html_content = self._add_css_classes(html_content)

                doc = {
                    'slug': slug,
                    'title': front_matter.get('title', slug),
                    'category': front_matter.get('category', 'Uncategorized'),
                    'order': front_matter.get('order', 999),
                    'content': html_content,
                    'toc': getattr(self.md, 'toc', ''),
                    'meta': front_matter
                }

                docs[slug] = doc
                self._cache_doc(slug, doc)

            except Exception as e:
                logger.error(f"Error loading markdown file {
                             file_path}: {str(e)}")
                continue

        return docs

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """Parse frontmatter and content from a markdown file."""
        # Normalize line endings
        content = content.replace('\r\n', '\n')

        # Check for frontmatter markers
        if not content.startswith('---'):
            return {}, content

        try:
            # Split on frontmatter markers, handling potential spaces
            parts = content.split('---')
            if len(parts) < 3:
                return {}, content

            # Get the frontmatter content (second part) and remaining content (third part onwards)
            frontmatter = parts[1].strip()
            content = '---'.join(parts[2:]).strip()

            # Parse the frontmatter
            metadata = yaml.safe_load(frontmatter)
            if not metadata:
                return {}, content

            # Ensure category_order is present
            if 'category_order' not in metadata:
                # Set default order based on category
                default_orders = {
                    'Overview': 1,
                    'API Reference': 2,
                    'Guides': 3
                }
                metadata['category_order'] = default_orders.get(
                    metadata.get('category', ''),
                    999
                )

            return metadata, content

        except Exception as e:
            logger.error(f"Error parsing frontmatter: {str(e)}")
            # Return empty frontmatter and original content on error
            return {}, content

    def _cache_doc(self, slug: str, doc: dict) -> None:
        """Cache a document in both memory and Redis."""
        self.docs_cache[slug] = doc
        try:
            redis_client.setex(
                f"docs:{slug}",
                current_app.config.get('DOCS_CACHE_TTL', 3600),
                json.dumps(doc)
            )
        except Exception as e:
            logger.error(f"Error caching doc in Redis: {str(e)}")

    def _get_cached_doc(self, slug: str) -> Optional[dict]:
        """Get a document from cache (memory or Redis)."""
        if slug in self.docs_cache:
            return self.docs_cache[slug]

        try:
            cached = redis_client.get(f"docs:{slug}")
            if cached:
                doc = json.loads(cached)
                self.docs_cache[slug] = doc
                return doc
        except Exception as e:
            logger.error(f"Error getting doc from Redis: {str(e)}")

        return None

    def get_doc(self, slug: str) -> Optional[Dict]:
        """Get a specific document by slug."""
        doc = self._get_cached_doc(slug)
        if doc:
            return doc

        docs = self.load_docs()
        return docs.get(slug)

    def _get_title(self, content: str) -> str:
        """Extract title from content."""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        return match.group(1) if match else ''

    def get_category_tree(self) -> Dict[str, List[Dict]]:
        """Get documentation organized by categories."""
        docs = self.load_docs()
        tree = {}

        for doc in docs.values():
            category = doc['category']
            if category not in tree:
                tree[category] = []
            tree[category].append({
                'slug': doc['slug'],
                'title': doc['title'],
                'order': doc['order']
            })

        # Sort categories and docs within categories
        for category in tree.values():
            category.sort(key=lambda x: (x['order'], x['title']))

        return dict(sorted(tree.items()))

    def search_docs(self, query: str) -> List[Dict]:
        """Search documentation."""
        docs = self.load_docs()
        results = []

        for doc in docs.values():
            if (query.lower() in doc['title'].lower() or
                    query.lower() in doc['content'].lower()):
                results.append({
                    'slug': doc['slug'],
                    'title': doc['title'],
                    'category': doc['category'],
                    'excerpt': self._get_excerpt(doc['content'], query)
                })

        return results

    def get_category_tree(self) -> Dict[str, List[Dict]]:
        """Get documentation organized by categories with proper ordering."""
        docs = self.load_docs()
        tree = {}
        category_orders = {}  # Store category orders

        # First pass: collect categories and their orders
        for doc in docs.values():
            category = doc['category']
            # Get category order from any document in the category
            if category not in category_orders:
                category_orders[category] = doc['meta'].get(
                    'category_order', 999)

            if category not in tree:
                tree[category] = []

            tree[category].append({
                'slug': doc['slug'],
                'title': doc['title'],
                'order': doc['order']
            })

        # Sort documents within each category
        for category in tree:
            tree[category].sort(key=lambda x: (x['order'], x['title']))

        # Convert to sorted list of tuples and then back to dict to maintain order
        sorted_categories = sorted(
            tree.items(),
            key=lambda x: (
                category_orders.get(x[0], 999),  # First sort by category_order
                x[0]  # Then by category name
            )
        )

        return dict(sorted_categories)

    def _get_excerpt(self, content: str, query: str, length: int = 200) -> str:
        """Get a relevant excerpt from content containing the query."""
        text = re.sub(r'<[^>]+>', '', content)
        pos = text.lower().find(query.lower())

        if pos == -1:
            return text[:length] + '...'

        start = max(0, pos - length // 2)
        end = min(len(text), pos + length // 2)
        excerpt = text[start:end]

        if start > 0:
            excerpt = '...' + excerpt
        if end < len(text):
            excerpt = excerpt + '...'

        return excerpt
