% git, code

# 切换分支

```sh
git checkout <branch>
```

$ branch: git branch | awk '{print $NF}'

---

% docker, run

# 运行容器并映射端口

```sh
docker run -it --rm -p <host_port>:<container_port> <image>
```

$ host_port: echo "3000 8080 9000" | tr ' ' '\n'
$ container_port: echo "3000 8080 9000" | tr ' ' '\n'
$ image: docker images --format "{{.Repository}}:{{.Tag}}" | grep -v "<none>"
