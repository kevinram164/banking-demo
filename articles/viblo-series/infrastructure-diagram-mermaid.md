# Sơ đồ tổ chức hạ tầng — Banking Demo

## Hình ảnh (đã render)

File ảnh dùng cho Viblo: **`assets/banking-demo-infrastructure-diagram.png`**

Trong Viblo: vào bài viết → chèn ảnh → upload file này hoặc kéo thả.

---

## Mermaid (dùng trong Viblo nếu hỗ trợ code block Mermaid)

Copy đoạn dưới vào Viblo, đặt trong code block với language `mermaid`:

```mermaid
flowchart LR
    subgraph Internet[" "]
        User[User / Client]
    end

    subgraph LB["Load Balancer"]
        Nginx["Nginx LB<br/>10.100.1.100"]
    end

    subgraph K8s["Kubernetes Cluster"]
        Master["Master<br/>10.100.1.120"]
        subgraph Workers["Workers"]
            W1["Worker01<br/>10.100.1.121"]
            W2["Worker02<br/>10.100.1.122"]
            W3["Worker03<br/>10.100.1.123"]
        end
        Route["Worker-Route<br/>10.100.1.45"]
    end

    subgraph Storage["Storage"]
        NFS["NFS<br/>10.100.1.180"]
    end

    User --> Nginx
    Nginx --> Master
    Nginx --> W1
    Nginx --> W2
    Nginx --> W3
    Master --> W1
    Master --> W2
    Master --> W3
    W1 --> Route
    W2 --> Route
    W3 --> Route
    W1 --> NFS
    W2 --> NFS
    W3 --> NFS
```

---

## Phiên bản đơn giản (chỉ các node + IP)

```mermaid
flowchart TB
    subgraph LB
        A["Nginx LB - 10.100.1.100"]
    end

    subgraph Control
        B["Master - 10.100.1.120"]
    end

    subgraph Compute
        C["Worker01 - 10.100.1.121"]
        D["Worker02 - 10.100.1.122"]
        E["Worker03 - 10.100.1.123"]
        F["Worker-Route - 10.100.1.45"]
    end

    subgraph Storage
        G["NFS - 10.100.1.180"]
    end

    A --> B
    A --> C
    A --> D
    A --> E
    B --> C
    B --> D
    B --> E
    C --> G
    D --> G
    E --> G
```

---

## Bảng tóm tắt (chèn vào bài Viblo)

| Vai trò        | Host        | IP           |
|----------------|-------------|--------------|
| Nginx LB       | (LB)        | 10.100.1.100 |
| Master         | Master      | 10.100.1.120 |
| Worker 1       | Worker01    | 10.100.1.121 |
| Worker 2       | Worker02    | 10.100.1.122 |
| Worker 3       | Worker03    | 10.100.1.123 |
| Worker-Route   | Worker-route| 10.100.1.45  |
| NFS            | NFS         | 10.100.1.180 |
