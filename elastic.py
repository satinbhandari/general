Yes, you can update existing documents in an Elasticsearch index, including modifying the contents (fields) of those documents. There are a few ways to do it, depending on how many documents you're updating:


---

1. Update a Single Document

If you know the document's _id, you can update its content:

POST /your_index_name/_update/your_doc_id
{
  "doc": {
    "old_field_name": null,
    "new_field_name": "new_value"
  }
}

Setting "old_field_name": null effectively removes the old field.

Adding "new_field_name" adds/updates that field.



---

2. Update by Query (Bulk Update)

If you want to update multiple documents based on a query, use _update_by_query:

POST /your_index_name/_update_by_query
{
  "script": {
    "source": """
      ctx._source.new_field_name = ctx._source.remove('old_field_name');
    """,
    "lang": "painless"
  },
  "query": {
    "exists": {
      "field": "old_field_name"
    }
  }
}

This will:

Move old_field_name to new_field_name

Remove old_field_name



---

Important Notes:

Field names in mappings remain—if old_field_name exists in mapping, it won’t be removed unless you reindex.

You can’t rename fields at the mapping level—only reindexing achieves that.



---

If you let me know:

Your index name

The field(s) to rename

Optional query filter


…I can generate the exact update script for you. Want to go that route?

