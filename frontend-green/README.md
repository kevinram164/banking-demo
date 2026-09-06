# Frontend GREEN (blue-green demo)

Folder này = **version mới**, độc lập với [`../frontend`](../frontend) (version cũ / blue).

| | Blue (ổn định) | Green (mới) |
|--|----------------|-------------|
| Code | `banking-demo/frontend/` | `banking-demo/frontend-green/` |
| Image Harbor | `.../banking-demo/frontend` | `.../banking-demo/frontend-green` |
| Deploy | `frontend-blue` | `frontend-green` |

```bash
REG=harbor-platform.apps.ocp01.npd.co/banking-demo
TAG=9b04db8

docker build -t $REG/frontend:$TAG ./frontend
docker build -t $REG/frontend-green:$TAG ./frontend-green
docker push $REG/frontend:$TAG
docker push $REG/frontend-green:$TAG
```

**Jenkins:** `BUILD_TARGET=frontend-green` (sau khi push shared lib `Projects.groovy`). Auto khi đổi file dưới `frontend-green/`.

Mesh / weight: [`phase9-gitops-platform/mesh/BLUE-GREEN-BANKING-FRONTEND.md`](../phase9-gitops-platform/mesh/BLUE-GREEN-BANKING-FRONTEND.md)
