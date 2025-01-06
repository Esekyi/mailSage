# app/routes/docs.py
from flask import Blueprint, jsonify, request, current_app
from app.services.docs_loader import DocsLoader

docs_bp = Blueprint('docs', __name__, url_prefix='/api/v1/docs')
docs_loader = None


@docs_bp.before_app_request
def initialize_docs():
    global docs_loader
    if docs_loader is None:
        docs_loader = DocsLoader()
        docs_loader.load_docs()


@docs_bp.route('', methods=['GET'])
def list_docs():
    """Get the documentation category tree."""
    if docs_loader is None:
        initialize_docs()
    tree = docs_loader.get_category_tree()
    return jsonify(tree)


@docs_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get documentation categories."""
    if docs_loader is None:
        initialize_docs()
    tree = docs_loader.get_category_tree()
    return jsonify(tree)


@docs_bp.route('/<path:slug>', methods=['GET'])
def get_doc(slug):
    """Get a specific documentation page."""
    if docs_loader is None:
        initialize_docs()
    doc = docs_loader.get_doc(slug)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    return jsonify(doc)


@docs_bp.route('/search', methods=['GET'])
def search_docs():
    """Search documentation."""
    if docs_loader is None:
        initialize_docs()
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Search query is required"}), 400

    results = docs_loader.search_docs(query)
    return jsonify({
        "results": results,
        "count": len(results)
    })
