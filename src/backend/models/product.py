"""商品销售与广告表现 ORM 模型(M4.4)。

模块职责:
    1. 定义 ``ProductSale`` ORM,映射 ``product_sales`` 表——
       记录各平台（Amazon / Shopee / AliExpress）的日粒度销售数据。
    2. 定义 ``AdPerformance`` ORM,映射 ``ad_performance`` 表——
       记录各平台广告投放表现（展示、点击、花费、转化）。
    3. 与 :class:`backend.models.user.User` 共享同一个 ``Base.metadata``,
       使 ``metadata.create_all(engine)`` 一次调用建所有表。

设计要点:
    - Base 从 ``backend.models.user`` 导入,不重复创建(YAGNI)。
    - 列结构根据 TechSPEC §7.5 示例查询 + 跨境电商领域常识推导。
    - ``acos`` / ``ctr`` / ``cpc`` 为计算列,由 ``init_data.py`` 写入;
      ORM 层不设 ``@property`` 计算（读多写少,写入时算一次更高效）。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.user import Base


class ProductSale(Base):
    """``product_sales`` 表 ORM 映射。

    字段:
        id:          自增主键。
        platform:    平台（Amazon / Shopee / AliExpress）。
        asin:        商品标识（ASIN / SKU）。
        title:       商品标题。
        category:    商品类目。
        date:        销售日期。
        currency:    币种（USD / SGD / CNY）。
        sales:       销售额。
        units:       订单数量。
        page_views:  页面浏览量。
        sessions:    访客数（独立会话）。
    """

    __tablename__ = "product_sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asin: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    sales: Mapped[float] = mapped_column(Float, nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    page_views: Mapped[int] = mapped_column(Integer, nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<ProductSale id={self.id} platform={self.platform!r} "
            f"asin={self.asin!r} date={self.date!r}>"
        )


class AdPerformance(Base):
    """``ad_performance`` 表 ORM 映射。

    字段:
        id:          自增主键。
        platform:    平台。
        asin:        商品标识。
        campaign:    广告活动名称。
        ad_type:     广告类型（SP / SB / SD）。
        date:        日期。
        impressions: 展示量。
        clicks:      点击量。
        spend:       广告花费。
        ad_sales:    广告带来的销售额。
        orders:      广告订单数。
        acos:        广告销售成本比（spend / ad_sales）。
        ctr:         点击率（clicks / impressions）。
        cpc:         单次点击成本（spend / clicks）。
    """

    __tablename__ = "ad_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asin: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    campaign: Mapped[str] = mapped_column(String(100), nullable=False)
    ad_type: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False)
    spend: Mapped[float] = mapped_column(Float, nullable=False)
    ad_sales: Mapped[float] = mapped_column(Float, nullable=False)
    orders: Mapped[int] = mapped_column(Integer, nullable=False)
    acos: Mapped[float] = mapped_column(Float, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, nullable=False)
    cpc: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<AdPerformance id={self.id} platform={self.platform!r} "
            f"asin={self.asin!r} campaign={self.campaign!r} date={self.date!r}>"
        )


__all__ = ["ProductSale", "AdPerformance"]
