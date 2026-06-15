# TechZone Quick Start - Hướng Dẫn Nhanh

## 🎯 Chọn Environment Nào?

Dựa vào screenshot TechZone của bạn, đây là các options có sẵn:

### ⭐ **KHUYẾN NGHỊ: "OpenShift Cluster OCPv IBM Cloud"**

```
✅ CHỌN CÁI NÀY!
Environment - OCP-V on IBM Cloud
OpenShift Cluster OCPv IBM Cloud
```

**Lý do:**
- ✅ OpenShift trên IBM Cloud (giống production)
- ✅ Base OpenShift UPI cluster
- ✅ Có 4-18 workers (đủ cho Banking Demo)
- ✅ Certified environment
- ✅ Dễ setup và sử dụng

### 📋 Các Options Khác (Tham Khảo)

| Option | Mô Tả | Phù Hợp? |
|--------|-------|----------|
| **AWS OpenShift Cluster** | OpenShift trên AWS | ⚠️ Không phải IBM Cloud |
| **OCP-V On-prem** | OpenShift on-premise | ⚠️ Phức tạp hơn |
| **Single Node OpenShift** | 1 node only (Beta) | ❌ Không đủ cho Banking Demo |
| **Red Hat OpenShift on IBM Z** | Mainframe | ❌ Quá phức tạp |

## 🚀 Các Bước Reserve

### Bước 1: Chọn Environment

```
1. Trong TechZone, tìm và click vào:
   "Environment - OCP-V on IBM Cloud"
   "OpenShift Cluster OCPv IBM Cloud"

2. Click nút "Reserve" (màu xanh)
```

### Bước 2: Điền Thông Tin Reservation

```
Purpose: Education
   → Chọn "Education" hoặc "Practice / Self-Education"

Preferred Geography: 
   → Chọn "AMERICAS" (gần nhất với bạn)
   → Hoặc "APAC" nếu ở châu Á

Duration:
   → Chọn "2 weeks" (có thể extend sau)

Description:
   → Viết: "Learning Banking Demo deployment on OpenShift"

Opportunity Number (optional):
   → Để trống nếu không có
```

### Bước 3: Submit Reservation

```
1. Review thông tin
2. Accept Terms and Conditions
3. Click "Submit"
4. Đợi email confirmation (5-30 phút)
```

### Bước 4: Access Cluster

Sau khi nhận email "Your environment is ready":

```
1. Vào TechZone → My Reservations
2. Click vào reservation của bạn
3. Tìm section "Access Information"
4. Copy "OpenShift Console URL"
5. Copy "Login Command"
```

### Bước 5: Login vào OpenShift

#### Option A: Web Console
```
1. Mở OpenShift Console URL trong browser
2. Login bằng credentials từ email
3. Explore Web Console
```

#### Option B: CLI (Recommended)
```bash
# Copy login command từ TechZone
# Nó sẽ giống như:
oc login --token=sha256~xxxxx --server=https://api.xxx.cloud.ibm.com:6443

# Verify
oc whoami
oc get nodes
oc get projects
```

## 📦 Deploy Banking Demo

### Bước 1: Tạo Project

```bash
# Tạo project (namespace)
oc new-project banking

# Verify
oc project banking
```

### Bước 2: Clone Repository

```bash
# Clone banking demo
git clone <your-banking-demo-repo>
cd banking-demo
```

### Bước 3: Deploy Application

```bash
# Apply Kubernetes manifests
oc apply -f k8s/secret.yaml
oc apply -f k8s/postgres.yaml
oc apply -f k8s/redis.yaml
oc apply -f k8s/kong.yaml
oc apply -f k8s/auth-service.yaml
oc apply -f k8s/account-service.yaml
oc apply -f k8s/transfer-service.yaml
oc apply -f k8s/notification-service.yaml
oc apply -f k8s/frontend.yaml
```

### Bước 4: Tạo Routes (OpenShift-specific)

```bash
# Expose frontend
oc expose service frontend --name=banking-frontend

# Expose Kong API
oc expose service kong --name=banking-api --port=8000

# Get Routes
oc get routes
```

### Bước 5: Access Application

```bash
# Get frontend URL
oc get route banking-frontend -o jsonpath='{.spec.host}'

# Access trong browser
# https://banking-frontend-banking.apps.<cluster-domain>
```

## 🔍 Verify Deployment

```bash
# Check all pods
oc get pods -n banking

# Check services
oc get svc -n banking

# Check routes
oc get routes -n banking

# Check logs
oc logs -f deployment/auth-service -n banking
```

## 📊 Monitoring

```bash
# OpenShift có built-in monitoring
# Access từ Web Console:
# Observe → Dashboards

# Hoặc dùng CLI
oc adm top nodes
oc adm top pods -n banking
```

## ⏱️ Extend Reservation

Nếu cần thêm thời gian:

```
1. Vào TechZone → My Reservations
2. Click vào reservation
3. Click "Extend"
4. Chọn thêm 1-2 tuần
5. Submit
```

## 🆘 Troubleshooting

### Không nhận được email
```
- Check spam folder
- Đợi thêm 30 phút
- Contact TechZone support
```

### Không login được cluster
```bash
# Get new login token từ OpenShift Console
# Click username (top right) → Copy login command
```

### Pods không start
```bash
# Check pod status
oc get pods -n banking

# Describe pod
oc describe pod <pod-name> -n banking

# Check logs
oc logs <pod-name> -n banking

# Check events
oc get events -n banking --sort-by='.lastTimestamp'
```

### SCC (Security Context Constraints) issues
```bash
# OpenShift có security policies nghiêm ngặt
# Nếu pod không start do SCC:

# Check SCC
oc get scc

# Add SCC to service account
oc adm policy add-scc-to-user anyuid \
  system:serviceaccount:banking:default
```

## 📚 Tài Liệu Tham Khảo

- [TechZone Portal](https://techzone.ibm.com)
- [OpenShift Documentation](https://docs.openshift.com/)
- [oc CLI Reference](https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html)

## 💡 Tips

### 1. Save Credentials
```bash
# Save login command
echo "oc login --token=xxx --server=xxx" > login.sh
chmod +x login.sh
```

### 2. Use Web Console
```
OpenShift Web Console rất mạnh:
- Visual topology view
- Built-in monitoring
- Log viewer
- Terminal access to pods
```

### 3. Explore OpenShift Features
```bash
# Try OpenShift-specific features:
- Routes (thay vì Ingress)
- ImageStreams
- BuildConfigs
- DeploymentConfigs
```

### 4. Backup Important Data
```bash
# Export configurations
oc get all -n banking -o yaml > banking-backup.yaml

# Export secrets (careful!)
oc get secrets -n banking -o yaml > secrets-backup.yaml
```

## 🎓 Learning Resources

### OpenShift Basics
- [OpenShift Interactive Learning](https://learn.openshift.com/)
- [OpenShift Tutorials](https://docs.openshift.com/container-platform/latest/getting_started/index.html)

### Banking Demo Specific
- Đọc: `ibm-cloud-deployment/03-openshift/README.md`
- Xem: `MICROSERVICES.md` trong repo

## ✅ Checklist

### Before Starting:
- [ ] Đã reserve TechZone environment
- [ ] Đã nhận email confirmation
- [ ] Đã có oc CLI installed
- [ ] Đã clone banking-demo repo

### During Deployment:
- [ ] Đã login vào cluster
- [ ] Đã tạo project "banking"
- [ ] Đã deploy tất cả services
- [ ] Đã tạo routes
- [ ] Đã verify pods running

### After Deployment:
- [ ] Đã test application
- [ ] Đã explore OpenShift features
- [ ] Đã backup configurations
- [ ] Đã document learnings

## 🔄 Next Steps

1. ✅ Reserve TechZone OpenShift cluster
2. ✅ Deploy Banking Demo
3. ✅ Explore OpenShift features
4. ✅ Try Tekton Pipelines (built-in CI/CD)
5. ✅ Setup monitoring
6. ✅ Document your experience

---

**Happy Learning! 🎓**

*TechZone + OpenShift = Perfect combination for learning!*