from flask import Flask, request, jsonify
import subprocess
import json
import yaml

from entity.repo_image import RepoImage

app = Flask(__name__)

# 配置阿里云仓库地址
ALIYUN_REGISTRY = "crpi-lsey5sghxxwk05fh.cn-hangzhou.personal.cr.aliyuncs.com"
APP_NAMESPACE = "app_ns"

# yml的存放路径
YML_FILE_PATH = "/app/InsuranceApp/docker-compose.yml"
SERVICE_NAME = "insure-app"

# 查询当前镜像版本
@app.route("/image/version", methods=["GET"])
def get_image_version():
    with open(YML_FILE_PATH, "r") as f:
        compose_config = yaml.safe_load(f)

    image = compose_config["services"][SERVICE_NAME]["image"]
    return jsonify({"status": "success", "image": image})

# 修改镜像版本
@app.route("/container/update", methods=["POST"])
def update_image_version():
    new_version = request.json.get("version")
    repo_name = request.json.get("repo_name")
    if not new_version:
        return jsonify({"status": "error", "message": "Missing version"}), 400
    if not repo_name:
        return jsonify({"status": "error", "message": "Missing repo name"}), 400

    with open(YML_FILE_PATH, "r") as f:
        compose_config = yaml.safe_load(f)

    new_image = f"{repo_name}:{new_version}"
    compose_config["services"][SERVICE_NAME]["image"] = new_image

    with open(YML_FILE_PATH, "w") as f:
        yaml.dump(compose_config, f, default_flow_style=False)

    # 拉取远端镜像，校验远端和本地缓存的image id是否相同，如果相同则使用本地缓存的镜像。
    subprocess.check_output(
        f'docker-compose -f {YML_FILE_PATH} pull',
        shell=True,
        encoding="utf-8"
    )

    # 重建容器
    subprocess.check_output(
        f'docker-compose -f {YML_FILE_PATH} up -d',
        shell=True,
        encoding="utf-8"
    )

    # 查看是否存在无头镜像
    result = subprocess.check_output(
        "docker images | grep '<none>' | awk '{print $3}'",
        shell=True,
        encoding="utf-8"
    )

    if result:
        # 存在无头镜像则删除逻辑
        subprocess.check_output(
            "docker images | grep '<none>' | awk '{print $3}' | xargs docker rmi -f",
            shell=True,
            encoding="utf-8"
        )

    return jsonify({"status": "success", "new_image": new_image})

# 查询本地镜像列表
@app.route("/images", methods=["GET"])
def list_images():
    try:
        # 获取镜像列表，每一行是一个 JSON
        result = subprocess.check_output(
            'docker images --format "{{json .}}"',
            shell=True,
            encoding="utf-8"
        )
        # 每行一个 JSON，逐行解析
        images = []
        for line in result.strip().split("\n"):
            if line:
                image_info = json.loads(line)
                repo_image = RepoImage(image_info['ID'], image_info['Repository'], image_info['Tag'])
                images.append(repo_image.to_dict())

        return jsonify({"status": "success", "data": images})

    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)})


# 打 tag、push、删除临时 tag
@app.route("/push-image", methods=["POST"])
def push_image():
    data = request.get_json()
    local_image = data.get("local_image")
    version = data.get("version")

    re_version = data.get("re_version")

    if not local_image or not version:
        return jsonify({"status": "error", "message": "缺少 local_image 或 version 参数"}), 400

    aliyun_image = f"{ALIYUN_REGISTRY}/{APP_NAMESPACE}/{local_image}:{re_version or version}"

    try:
        # 打 tag
        subprocess.check_call(["docker", "tag", f"{local_image}:{version}", aliyun_image])

        # 推送
        subprocess.check_call(["docker", "push", aliyun_image])

        # 删除 tag 镜像
        subprocess.check_call(["docker", "rmi", aliyun_image])

        return jsonify({"status": "success", "message": f"{aliyun_image} 已推送并清理"}), 200

    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 拉取镜像
@app.route("/pull-images", methods=["POST"])
def pull_images():
    data = request.get_json()
    repo_name = data.get("repo_name")
    tag = data.get("tag")

    rename_repo_name = data.get("rename_repo_name")
    re_tag = data.get("re_tag")

    remote_repo_addr = f"{ALIYUN_REGISTRY}/{APP_NAMESPACE}/{repo_name}:{tag}"

    try:
        # 拉取
        subprocess.check_call(["docker", "pull", remote_repo_addr])
        # 判断是否重命名或者重新打tag
        if rename_repo_name or re_tag:
            # docker重命名
            subprocess.check_call(["docker", "tag", remote_repo_addr, f"{rename_repo_name}:{re_tag or tag}"])
            # 删除重命名后的镜像，删除下载镜像。
            subprocess.check_call(["docker", "rmi", remote_repo_addr])
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "success", "data": f"镜像拉取成功，本地已保存镜像为：{rename_repo_name}:{re_tag or tag}"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000)
