"""Finbot SQL MCP server package.

Exposes the finbot banking data held in the **Fabric SQL Database**
``finbot-data-2`` over the Model Context Protocol. The data is queried **live**
via managed identity — it is never bundled into the image or committed to the
repository.
"""
