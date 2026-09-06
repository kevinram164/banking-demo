# HTTPRoute weight snippets — copy vào banking-frontend-bluegreen.yaml rồi sync mesh-waypoint

## B0 — baseline 100/0
```yaml
        - name: frontend-blue
          port: 80
          weight: 100
        - name: frontend-green
          port: 80
          weight: 0
```

## B1 — 70/30
```yaml
        - name: frontend-blue
          port: 80
          weight: 70
        - name: frontend-green
          port: 80
          weight: 30
```

## B2 — 50/50
```yaml
        - name: frontend-blue
          port: 80
          weight: 50
        - name: frontend-green
          port: 80
          weight: 50
```

## B3 — 30/70
```yaml
        - name: frontend-blue
          port: 80
          weight: 30
        - name: frontend-green
          port: 80
          weight: 70
```

## B4 — cutover 0/100
```yaml
        - name: frontend-blue
          port: 80
          weight: 0
        - name: frontend-green
          port: 80
          weight: 100
```
