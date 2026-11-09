Ảnh đính kèm (theo thứ tự): assets/fb-vault-injector-cover.jpg, assets/fb-vault-injector-howitworks.jpg, assets/fb-vault-vs-eso.jpg

---

Mấy hôm nay mình dựng lại cụm k8s lab và có đổi một chỗ khá lớn: bỏ External Secrets Operator (ESO), chuyển sang dùng Vault Agent Injector để đưa secret vào pod. Viết lại đây cho ai đang phân vân giữa 2 cách này.

Trước đây mình dùng Vault + ESO. ESO đọc secret trong Vault rồi tạo ra Secret của k8s, pod cứ thế dùng env như bình thường. Tiện, app không phải sửa gì. Nhưng dùng một thời gian thì thấy hơi ngược: đã cất mật khẩu vào Vault cho an toàn, cuối cùng nó vẫn nằm trong etcd dưới dạng base64. Ai có quyền get secret trong namespace là đọc được hết. Chưa kể ESO dùng chung một token để đọc Vault cho tất cả app, hồi lab mình còn để luôn token root cho nhanh 😅

Vault Agent Injector thì làm khác. Trong manifest mình chỉ thêm vài annotation cho pod. Lúc pod được tạo, webhook của Vault tự chèn thêm một init container. Container này lấy token ServiceAccount của chính pod mang lên Vault login, Vault hỏi lại k8s xem đây là SA nào, namespace nào, rồi chỉ trả về đúng secret mà role của SA đó được phép đọc. Secret được ghi ra file trong /vault/secrets, nằm trên RAM của pod, không có Secret nào trong etcd cả.

Kết quả là movie-api chỉ đọc được secret của movie-api, Jenkins không đọc được mật khẩu DB, mỗi app một role riêng. Mở log audit của Vault ra cũng thấy rõ app nào đọc cái gì.

Đổi lại cũng mệt hơn chút. App phải tự đọc secret từ file. Với app Python thì mình source file env trước khi chạy uvicorn, Grafana thì có sẵn cú pháp $__file{}, còn cloudflared là image distroless không có shell nên phải dùng --token-file. Secret để pull image từ Harbor thì vẫn phải tạo Secret k8s như cũ, vì kubelet pull image trước khi agent kịp chạy. Và cái mình dính nhiều nhất: Vault mà sealed hoặc quên tạo role là pod mới kẹt Init:0/1 hết, ngồi đọc log init container mới ra.

Nói thêm về Vault Enterprise, vì làm xong lab mình mới thấy rõ mấy chỗ bản open source bắt đầu đuối khi lên môi trường thật:

- Namespaces: lab của mình đang cho banking, shop, cinehome... dùng chung một mount secret/ và chia nhau bằng path. Bản Enterprise có namespace, mỗi team một "Vault con" riêng với policy, auth method, admin riêng, không phải ngồi viết policy chặn chéo nhau.
- Replication: bản OSS mình chỉ chạy một instance, Vault chết là cả cluster không start được pod mới (đúng cái nhược điểm của Injector ở trên). Enterprise có DR replication để có cụm dự phòng, performance replication và performance standby để các region/cụm khác đọc secret tại chỗ, đỡ phụ thuộc vào một chỗ.
- Sentinel: viết policy dạng code, kiểu chỉ cho đọc secret production từ dải IP CI, hoặc trong giờ hành chính. ACL thường không làm được mấy điều kiện này.
- Thêm vài thứ như control group (đọc secret nhạy cảm phải có người duyệt), auto-unseal bằng HSM, seal wrap cho các bên cần FIPS.

Còn auto-unseal qua cloud KMS thì bản OSS cũng có, chỉ là lab của mình đang unseal tay. Nếu không muốn tự vận hành thì có HCP Vault Dedicated, bản managed có sẵn các tính năng Enterprise.

Tóm lại: nếu chỉ dùng Vault và app phần lớn do team tự viết thì Injector rất đáng thử. Còn nếu dùng nhiều nơi lưu secret (AWS, GCP, Azure...) hoặc nhiều Helm chart chỉ nhận existingSecret thì ESO vẫn hợp hơn. Lên production nhiều team, nhiều cụm thì nên tính tới Vault Enterprise hoặc HCP.

Bài chi tiết có sơ đồ từng bước, YAML thật và mấy lỗi Init:0/1 hay gặp mình để dưới comment. Mọi người đang quản lý secret trên k8s bằng gì, chia sẻ với mình với.

#Kubernetes #DevOps #HashiCorpVault #VaultEnterprise #CloudNative
