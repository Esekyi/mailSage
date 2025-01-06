import re
from pathlib import Path
from typing import Dict, List, Optional
import yaml
import markdown
from flask import current_app
from app.extensions import redis_client
from app.utils.logging import logger
import json


class DocsLoader:
    """Service for loading and managing markdown documentation."""

    def __init__(self, docs_dir: str = 'docs'):
        self.docs_dir = docs_dir
        self.docs_cache = {}  # In-memory cache
        self.md = markdown.Markdown(
            extensions=[
                'meta',
                'fenced_code',
                'tables',
                'toc',
                'attr_list',
                'def_list',
                'md_in_html',
            ],
            extension_configs={
                'codehilite': {
                    'css_class': 'language',
                    'use_pygments': False
                }
            }
        )

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

                # Process content for better formatting
                content = self._process_content(content)

                # Convert markdown to HTML
                self.md.reset()
                html_content = self.md.convert(content)

                # Add CSS classes
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
        content = content.replace('\r\n', '\n')

        if not content.startswith('---\n'):
            return {}, content

        try:
            _, frontmatter, *rest = content.split('---\n', 2)
            if rest:
                content = rest[0]
                return yaml.safe_load(frontmatter), content
            return {}, content
        except Exception as e:
            logger.error(f"Error parsing frontmatter: {str(e)}")
            return {}, content

    def _process_content(self, content: str) -> str:
        """Process markdown content to add proper spacing and formatting."""
        # Add spacing around headers
        content = re.sub(r'(^|\n)(#+ [^\n]+)', r'\1\n\2\n', content)

        # Improve table formatting
        content = re.sub(
            r'(\n\|[^\n]+\|)\n([^\n])',
            r'\1\n\n\2',
            content
        )

        # Ensure code blocks have language specified
        content = re.sub(
            r'```\s*\n',
            r'```text\n',
            content
        )

        # Add spacing around code blocks
        content = re.sub(
            r'(```[^\n]*\n.*?\n```)',
            r'\n\1\n',
            content,
            flags=re.DOTALL
        )

        return content

    def _add_css_classes(self, html_content: str) -> str:
        """Add CSS classes to HTML elements for better styling."""
        # Update code block handling
        html_content = re.sub(
            r'<pre><code class="language-([^"]+)"',
            r'<pre class="language-\1"><code class="language-\1"',
            html_content
        )

        # Add data-language attribute
        html_content = re.sub(
            r'<pre class="language-([^"]+)"',
            r'<pre class="language-\1" data-language="\1"',
            html_content
        )

        # Table styling
        html_content = html_content.replace(
            '<table>',
            '<div class="table-container"><table>'
        ).replace(
            '</table>',
            '</table></div>'
        )

        # Add classes to headings
        for i in range(1, 7):
            html_content = html_content.replace(
                f'<h{i}',
                f'<h{i} class="scroll-m-20"'
            )

        return html_content

    def get_doc(self, slug: str) -> Optional[Dict]:
        """Get a specific document by slug."""
        doc = self._get_cached_doc(slug)
        if doc:
            return doc

        docs = self.load_docs()
        return docs.get(slug)

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

        # Sort each category
        for category in tree.values():
            category.sort(key=lambda x: (x['order'], x['title']))

        return dict(sorted(tree.items()))

    def search_docs(self, query: str) -> List[Dict]:
        """Search documentation."""
        docs = self.load_docs()
        results = []

        for doc in docs.values():
            if (
                query.lower() in doc['title'].lower() or
                query.lower() in doc['content'].lower()
            ):
                results.append({
                    'slug': doc['slug'],
                    'title': doc['title'],
                    'category': doc['category'],
                    'excerpt': self._get_excerpt(doc['content'], query)
                })

        return results

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
