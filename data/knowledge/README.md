# 示例知识库（教学用）

把 `.md` / `.txt` 放到这个目录。服务第一次启动、索引还是空的时候，会自动灌进向量库。

之后也可以用 HTTP 追加：

```http
POST /knowledge
{"content": "……", "source": "my-note"}
```

试着问 Agent：「年假有几天？」或「HTTP 服务默认端口是多少？」
