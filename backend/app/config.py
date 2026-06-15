from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "123456"
    DB_NAME: str = "project_mgmt"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时

    # 企业微信
    WECHAT_WORK_CORP_ID: str = ""
    WECHAT_WORK_AGENT_ID: str = ""
    WECHAT_WORK_SECRET: str = ""

    # 微信公众号
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    WECHAT_TEMPLATE_ID: str = ""

    # 阿里云OSS
    OSS_ENABLED: bool = False
    OSS_ACCESS_KEY: str = ""
    OSS_SECRET_KEY: str = ""
    OSS_BUCKET: str = ""
    OSS_ENDPOINT: str = ""

    # 本地附件存储
    UPLOAD_DIR: str = "./uploads"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            "?charset=utf8mb4"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"  # 忽略 .env/环境变量里未定义的多余字段，避免部署时报错


settings = Settings()
