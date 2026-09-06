# Frontend (blue / ổn định)

FE production hiện tại. Blue-green: Deploy `frontend-blue` dùng image build từ **folder này**.

Version mới nằm riêng: [`../frontend-green`](../frontend-green) → image `.../frontend-green`.

```bash
docker build -t harbor-platform.apps.ocp01.npd.co/banking-demo/frontend:<tag> .
```
