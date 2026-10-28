from sqlalchemy import create_engine, Column, String, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
class Record(Base):
    __tablename__ = 'paper_signals'
    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)

class State(Base):
    __tablename__ = 'market_state'
    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)

class LiveRecord(Base):
    __tablename__ = 'mt5_paper_signals'
    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)

class LiveState(Base):
    __tablename__ = 'mt5_market_state'
    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)

class OandaRecord(Base):
    __tablename__ = 'oanda_paper_signals'
    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)

class OandaState(Base):
    __tablename__ = 'oanda_market_state'
    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)

class IntegrationCache(Base):
    __tablename__ = 'integration_cache'
    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)

class Store:
    def __init__(self, url, mode="simulated"):
        self.Record = Record if mode == "simulated" else LiveRecord
        self.State = State if mode == "simulated" else LiveState
        if mode.startswith("oanda:"):
            self.Record,self.State=OandaRecord,OandaState
        self.key = mode
        self.engine = create_engine(url, connect_args={'check_same_thread':False} if url.startswith('sqlite') else {}, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(self.engine)

    def load(self):
        with self.Session() as session:
            state = session.get(self.State,self.key)
            query=session.query(self.Record)
            if self.key.startswith("oanda:"):query=query.filter(self.Record.id.startswith(self.key+":"))
            signals = [r.data for r in query.all()]
            return state.data if state else None, sorted(signals,key=lambda s:s['created_at'])

    def save(self, state, signals):
        with self.Session.begin() as session:
            session.merge(self.State(id=self.key, data=state))
            for signal in signals:
                session.merge(self.Record(id=(self.key+":" if self.key.startswith("oanda:") else "")+signal['id'],data=signal))

    def load_cache(self, key):
        with self.Session() as session:
            row=session.get(IntegrationCache,key)
            return row.data if row else None

    def save_cache(self, key, data):
        with self.Session.begin() as session:
            session.merge(IntegrationCache(id=key,data=data))

    def close(self):
        self.engine.dispose()
