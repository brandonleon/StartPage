``` mermaid
erDiagram
    links }o--o{ tagmap : tags
    tagmap }o--o{ tags : tags
    config
    metadata

    links {
        varchar id
        text name
        text url
        float rank
        accessed datetime
    }

    config {
        text name
        text value
    }

    metadata {
        text name
        text value
    }

    tagmap {
        int linkid
        int tagid
    }

    tags {
        int id
        text name
    }
```
