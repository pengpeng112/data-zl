# Git 推送配置

仓库地址：git@github.com:pengpeng112/data-zl.git

## 推送命令（每次推送前执行）

```powershell
$env:GIT_SSH_COMMAND = "ssh -i F:/python/数据资产/.ssh/deploy_key -o StrictHostKeyChecking=yes -o UserKnownHostsFile=F:/python/数据资产/.ssh/known_hosts"
cd "F:\python\数据资产"
git push origin HEAD
```

## 拉取命令

```powershell
$env:GIT_SSH_COMMAND = "ssh -i F:/python/数据资产/.ssh/deploy_key -o StrictHostKeyChecking=yes -o UserKnownHostsFile=F:/python/数据资产/.ssh/known_hosts"
cd "F:\python\数据资产"
git pull --ff-only
```

- SSH 私钥：`F:/python/数据资产/.ssh/deploy_key`（已在 .gitignore 排除，不提交）
- SSH 公钥：`F:/python/数据资产/.ssh/deploy_key.pub`
- 公钥指纹：`SHA256:9OkGCsPcoT42p2237PZ/K8FI2cDm3pTWhWhequZk7i4`
- 首次连接前由运维确认 GitHub 主机指纹并写入 `.ssh/known_hosts`；禁止跳过主机密钥校验。
