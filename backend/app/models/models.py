from sqlalchemy import Column, String, Integer, Numeric, Date, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database.connection import Base

class Customer(Base):
    __tablename__ = 'customers'

    customer_id = Column(String(50), primary_key=True, index=True)
    segment = Column(String(50), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)

    orders = relationship("Order", back_populates="customer")

class Product(Base):
    __tablename__ = 'products'

    product_id = Column(String(50), primary_key=True, index=True)
    category = Column(String(100), nullable=False)
    product_name = Column(String(255), nullable=False)

    orders = relationship("Order", back_populates="product")

class Order(Base):
    __tablename__ = 'orders'

    order_id = Column(String(50), primary_key=True, index=True)
    customer_id = Column(String(50), ForeignKey('customers.customer_id'), nullable=False, index=True)
    product_id = Column(String(50), ForeignKey('products.product_id'), nullable=False, index=True)
    region = Column(String(50), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)  # Denormalized for fast analytics
    price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    order_date = Column(Date, nullable=False, index=True)

    customer = relationship("Customer", back_populates="orders")
    product = relationship("Product", back_populates="orders")

class Session(Base):
    __tablename__ = 'sessions'

    session_id = Column(String(50), primary_key=True, index=True)
    session_date = Column(Date, nullable=False, index=True)
    region = Column(String(50), nullable=False, index=True)
    segment = Column(String(50), nullable=False, index=True)
    sessions_count = Column(Integer, nullable=False)

# Add indexes for standard analysis combinations
Index('idx_order_date_region_category', Order.order_date, Order.region, Order.category)
Index('idx_session_date_region_segment', Session.session_date, Session.region, Session.segment)
