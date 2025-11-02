# API Error Shapes

## 400 Bad Request
```json
{
  "error": "bad_request",
  "message": "invalid query parameter 'limit', must be 1..100"
}

## 404 Not Found
{
  "error": "not_found",
  "message": "note not found"
}
