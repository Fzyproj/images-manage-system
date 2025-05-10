class RepoImage:
    # 构造函数
    def __init__(self, image_id, repo_name, tag):
        self.image_id = image_id
        self.repo_name = repo_name
        self.tag = tag

    # 用于结构体对象返回
    def to_dict(self):
        return {
            'image_id': self.image_id,
            'repo_name': self.repo_name,
            'tag': self.tag
        }
