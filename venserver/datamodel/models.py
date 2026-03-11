"""
SQLAlchemy models for VEN Server
Manages users, meter connections, and flexible resources for OpenADR VEN operations
"""
from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, String, DateTime, Float, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    """User role enumeration"""
    ADMIN = "admin"
    USER = "user"
    DATA_PROVIDER = "data_provider"  # Can register and update meter data


class ResourceType(str, enum.Enum):
    """Flexible resource types"""
    BATTERY = "battery"
    EV_CHARGER = "ev_charger"
    HEAT_PUMP = "heat_pump"
    HVAC = "hvac"
    SOLAR = "solar"
    WIND = "wind"
    LOAD = "load"
    GENERATOR = "generator"
    OTHER = "other"


class VTNRegistrationStatus(str, enum.Enum):
    """VTN registration status"""
    NOT_REGISTERED = "not_registered"
    PENDING = "pending"
    REGISTERED = "registered"
    FAILED = "failed"
    DEREGISTERED = "deregistered"


class ResourceStatusCode(str, enum.Enum):
    """Resource operational status codes"""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class VTNProgramEnrollmentStatus(str, enum.Enum):
    """Status of a resource's enrollment in a VTN program"""
    NOT_ENROLLED = "not_enrolled"
    PENDING = "pending"       # User requested enrollment; not yet confirmed by VTN
    ENROLLED = "enrolled"     # VTN confirmed enrollment
    FAILED = "failed"         # VTN returned an error
    UNENROLLED = "unenrolled" # Was enrolled, then removed


class User(Base):
    """
    User model for authentication and authorization.
    Supports Google OAuth authentication via email matching.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    # OAuth fields
    oauth_provider = Column(String(50))  # e.g., 'google'
    oauth_sub = Column(String(255))  # Subject identifier from OAuth provider

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime)

    # Relationships
    meter_connections = relationship("MeterConnection", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role}', is_admin={self.is_admin})>"

    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email

    @property
    def can_register_data(self):
        """Check if user has permission to register meter data"""
        return self.role in [UserRole.ADMIN, UserRole.DATA_PROVIDER] or self.is_admin


class MeterConnection(Base):
    """
    Represents a physical meter connection (AMS meter) at a specific address.
    Multiple flexible resources can share the same meter connection.
    """
    __tablename__ = "meter_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Meter identification
    meterpoint_id = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500))

    # Location data
    location_latitude = Column(Float)
    location_longitude = Column(Float)
    address1 = Column(String(200))
    address2 = Column(String(200))
    city = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(2), default="NO")  # ISO 3166-1 alpha-2

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship("User", back_populates="meter_connections")
    resources = relationship("FlexibleResource", back_populates="meter_connection", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MeterConnection(meterpoint_id='{self.meterpoint_id}', address='{self.address1}')>"

    @property
    def full_address(self):
        """Get formatted full address"""
        parts = [p for p in [self.address1, self.address2, self.city, self.postal_code, self.country] if p]
        return ", ".join(parts)


class FlexibleResource(Base):
    """
    Represents a flexible resource (battery, EV charger, heat pump, etc.)
    that can participate in demand response programs via OpenADR VTN.
    Each resource is registered individually at the VTN.
    """
    __tablename__ = "flexible_resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meter_connection_id = Column(UUID(as_uuid=True), ForeignKey("meter_connections.id"), nullable=False)

    # Resource identification
    resource_external_id = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500))
    resource_type = Column(SQLEnum(ResourceType), nullable=False)

    # VTN registration
    vtn_registration_status = Column(SQLEnum(VTNRegistrationStatus), default=VTNRegistrationStatus.NOT_REGISTERED, nullable=False)
    vtn_resource_id = Column(String(255))  # ID assigned by VTN when registered
    vtn_program_id = Column(String(255))  # OpenADR program this resource is enrolled in
    vtn_last_sync = Column(DateTime)  # Last successful sync with VTN

    # Technical specifications
    rated_power_kw = Column(Float)  # Maximum power capacity in kW
    energy_capacity_kwh = Column(Float)  # Energy storage capacity (for batteries)
    min_power_kw = Column(Float)  # Minimum operating power
    max_power_kw = Column(Float)  # Maximum operating power

    # Operational metadata
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text)  # Additional notes or configuration

    # Live heartbeat tracking (updated by modbus-worker via NATS)
    last_heartbeat_at = Column(DateTime, nullable=True)           # Last heartbeat received
    last_heartbeat_worker = Column(String(100), nullable=True)    # Worker ID that sent it

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    meter_connection = relationship("MeterConnection", back_populates="resources")
    status_history = relationship("ResourceStatus", back_populates="resource", cascade="all, delete-orphan",
                                 order_by="ResourceStatus.status_timestamp.desc()")

    def __repr__(self):
        return f"<FlexibleResource(external_id='{self.resource_external_id}', type='{self.resource_type}', vtn_status='{self.vtn_registration_status}')>"

    @property
    def current_status(self):
        """Get the most recent status entry"""
        return self.status_history[0] if self.status_history else None


class ResourceStatus(Base):
    """
    Historical status tracking for flexible resources.
    Records operational state changes and events.
    """
    __tablename__ = "resource_status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("flexible_resources.id"), nullable=False, index=True)

    status_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    status_code = Column(SQLEnum(ResourceStatusCode), nullable=False)

    # Additional status information
    message = Column(Text)  # Human-readable status message
    error_details = Column(Text)  # Error details if status is ERROR

    # Operational metrics at time of status
    power_kw = Column(Float)  # Current power draw/generation
    soc_percent = Column(Float)  # State of charge (for batteries)
    temperature_c = Column(Float)  # Temperature reading if applicable

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    resource = relationship("FlexibleResource", back_populates="status_history")

    def __repr__(self):
        return f"<ResourceStatus(resource_id='{self.resource_id}', status='{self.status_code}', timestamp='{self.status_timestamp}')>"


class AssetGroup(Base):
    """
    Groups of flexible resources (formerly Portfolios) managed collectively for
    demand response participation or optimization.
    """
    __tablename__ = "asset_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    members = relationship("AssetGroupMember", back_populates="group", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AssetGroup(name='{self.name}')>"


class AssetGroupMember(Base):
    """Membership link between AssetGroup and FlexibleResource."""
    __tablename__ = "asset_group_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("asset_groups.id"), nullable=False, index=True)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("flexible_resources.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    group = relationship("AssetGroup", back_populates="members")
    resource = relationship("FlexibleResource")


class SpotPrice(Base):
    """
    Hourly/quarterly spot prices per price area (e.g. NO1, NO2, NO3, NO4, NO5).
    Prices are in NOK/MWh (or EUR/MWh stored as-is, currency field clarifies).
    """
    __tablename__ = "spot_prices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    price_area = Column(String(20), nullable=False, index=True)   # e.g. "NO1"
    period_start = Column(DateTime, nullable=False, index=True)   # start of quarter/hour (UTC)
    period_end = Column(DateTime, nullable=False)
    price_nok_mwh = Column(Float, nullable=False)
    price_eur_mwh = Column(Float)
    currency = Column(String(10), default="NOK")
    resolution_minutes = Column(Float, default=60)               # 15 or 60
    source = Column(String(100))                                 # e.g. "entsoe", "nordpool"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SpotPrice(area='{self.price_area}', start='{self.period_start}', price={self.price_nok_mwh})>"


class GridCompany(Base):
    """
    A grid company (DSO / nettselskap) as listed in fri-nettleie.
    One row per company; identified by GLN number(s).
    The filename slug (e.g. 'elvia') is stored as source_slug for easy re-fetch.
    """
    __tablename__ = "grid_companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, index=True)       # e.g. "Elvia AS"
    source_slug = Column(String(100), unique=True, nullable=False, index=True)  # filename without .yml
    gln = Column(String(200))                                    # comma-separated GLN(s)
    sist_oppdatert = Column(String(20))                          # ISO date from YAML
    kilder = Column(Text)                                        # JSON list of source URLs

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tariff_periods = relationship("GridTariffPeriod", back_populates="company",
                                  cascade="all, delete-orphan",
                                  order_by="GridTariffPeriod.gyldig_fra")

    def __repr__(self):
        return f"<GridCompany(name='{self.name}', slug='{self.source_slug}')>"


class GridTariffPeriod(Base):
    """
    A single validity period within a company's tariff file.
    Maps to one entry in the 'tariffer' list in the fri-nettleie YAML.

    fastledd (capacity fee) is stored here as a step-function via GridFastleddTerskel.
    energiledd (energy fee) base price + any peak-hour exceptions are stored inline
    and via GridEnergileddUnntak.

    Prices:
      - fastledd terskler: NOK/year  (annual capacity fee per kW step)
      - energiledd grunnpris: øre/kWh
      - energiledd unntak pris: øre/kWh  (peak-hour override)
    """
    __tablename__ = "grid_tariff_periods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("grid_companies.id"),
                        nullable=False, index=True)

    # Customer group(s) this period applies to (JSON list, e.g. ["liten_næring","husholdning"])
    kundegrupper = Column(Text, nullable=False)

    # Validity window
    gyldig_fra = Column(DateTime, nullable=False, index=True)
    gyldig_til = Column(DateTime)                                # NULL = still valid

    # fastledd metadata
    fastledd_metode = Column(String(100))   # e.g. "TRE_DØGNMAX_MND"
    fastledd_terskel_inkludert = Column(Boolean, default=True)

    # energiledd
    energiledd_grunnpris_ore_kwh = Column(Float)                # base price øre/kWh
    energiledd_raw = Column(Text)                               # full JSON of energiledd block

    # raw snapshot
    raw_yaml = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("GridCompany", back_populates="tariff_periods")
    terskler = relationship("GridFastleddTerskel", back_populates="period",
                            cascade="all, delete-orphan",
                            order_by="GridFastleddTerskel.terskel_kw")
    unntak = relationship("GridEnergileddUnntak", back_populates="period",
                          cascade="all, delete-orphan")

    def __repr__(self):
        return (f"<GridTariffPeriod(company='{self.company_id}', "
                f"fra='{self.gyldig_fra}', kundegrupper='{self.kundegrupper}')>")

    @property
    def kundegrupper_list(self):
        import json as _j
        try:
            return _j.loads(self.kundegrupper)
        except Exception:
            return []

    def fastledd_nok_year(self, peak_kw: float) -> float:
        """
        Return the annual fastledd fee in NOK for a given peak-power level.
        Uses step-function: highest terskel that is <= peak_kw.
        """
        applicable = [t for t in self.terskler if t.terskel_kw <= peak_kw]
        if not applicable:
            return self.terskler[0].pris_nok_year if self.terskler else 0.0
        return max(applicable, key=lambda t: t.terskel_kw).pris_nok_year

    def fastledd_nok_month(self, peak_kw: float) -> float:
        return self.fastledd_nok_year(peak_kw) / 12.0

    def energiledd_ore_kwh(self, hour: int = 12, is_weekday: bool = True) -> float:
        """Return the energy tariff in øre/kWh for a given hour."""
        for u in self.unntak:
            if u.applies_to_hour(hour, is_weekday):
                return u.pris_ore_kwh
        return self.energiledd_grunnpris_ore_kwh or 0.0


class GridFastleddTerskel(Base):
    """
    One step (terskel) in the fastledd capacity-fee step function.
    terskel_kw: the lower bound of this step (kW peak usage).
    pris_nok_year: annual fee in NOK for customers in this step.
    """
    __tablename__ = "grid_fastledd_terskler"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id = Column(UUID(as_uuid=True), ForeignKey("grid_tariff_periods.id"),
                       nullable=False, index=True)
    terskel_kw = Column(Float, nullable=False)     # lower kW bound for this price step
    pris_nok_year = Column(Float, nullable=False)  # NOK/year

    period = relationship("GridTariffPeriod", back_populates="terskler")

    def __repr__(self):
        return f"<GridFastleddTerskel(terskel={self.terskel_kw} kW, pris={self.pris_nok_year} NOK/år)>"


class GridEnergileddUnntak(Base):
    """
    A time-of-use exception to the base energy price (energiledd).
    e.g. peak-hour surcharge on weekdays 06:00-21:00.
    """
    __tablename__ = "grid_energiledd_unntak"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id = Column(UUID(as_uuid=True), ForeignKey("grid_tariff_periods.id"),
                       nullable=False, index=True)

    navn = Column(String(100))              # e.g. "Virkedag"
    timer = Column(String(20))             # e.g. "6-21"
    dager = Column(Text)                   # JSON list, e.g. ["virkedag"]
    pris_ore_kwh = Column(Float, nullable=False)

    period = relationship("GridTariffPeriod", back_populates="unntak")

    def __repr__(self):
        return f"<GridEnergileddUnntak(navn='{self.navn}', timer='{self.timer}', pris={self.pris_ore_kwh})>"

    def applies_to_hour(self, hour: int, is_weekday: bool = True) -> bool:
        """Check whether this exception applies to a given hour."""
        import json as _j
        try:
            dager = _j.loads(self.dager) if self.dager else []
        except Exception:
            dager = []
        if "virkedag" in dager and not is_weekday:
            return False
        if "helg" in dager and is_weekday:
            return False
        if self.timer:
            parts = self.timer.split("-")
            if len(parts) == 2:
                try:
                    h_start, h_end = int(parts[0]), int(parts[1])
                    return h_start <= hour < h_end
                except ValueError:
                    pass
        return True



class VTNProgram(Base):
    """
    OpenADR programs fetched from the VTN and cached locally.
    Users can browse these and request enrollment of their resources.
    """
    __tablename__ = "vtn_programs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # VTN-assigned identifiers
    vtn_id = Column(String(255), unique=True, nullable=False, index=True)   # 'id' from VTN
    program_id = Column(String(255), index=True)                            # business-level program_id
    program_name = Column(String(500), nullable=False)
    program_long_name = Column(String(500))
    program_type = Column(String(100))
    program_priority = Column(Float, default=0)
    state = Column(String(50), default="PENDING")

    # Issuer / retailer
    program_issuer = Column(String(255))
    retailer_name = Column(String(255))
    retailer_long_name = Column(String(500))

    # Dates
    effective_start_date = Column(DateTime)
    effective_end_date = Column(DateTime)
    program_period_start = Column(DateTime)
    program_period_end = Column(DateTime)
    enrollment_period_start = Column(DateTime)
    enrollment_period_end = Column(DateTime)
    created_date = Column(DateTime)
    modification_date_time = Column(DateTime)

    # Geography
    country = Column(String(10))
    principal_subdivision = Column(String(100))
    timezone = Column(String(100), default="UTC")
    market_context = Column(String(255))
    participation_type = Column(String(100))

    # Notification / interval
    notification_time = Column(String(100))
    call_heads_up_time = Column(String(100))
    interval_period = Column(String(50), default="PT1H")
    interval_period_duration = Column(String(50))

    # Misc flags
    interruptible = Column(Boolean, default=False)

    # Raw JSON snapshot from VTN (for fields we don't map explicitly)
    raw_json = Column(Text)

    # Housekeeping
    last_synced_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    enrollments = relationship(
        "VTNProgramEnrollment", back_populates="program", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<VTNProgram(vtn_id='{self.vtn_id}', name='{self.program_name}', state='{self.state}')>"


class VTNProgramEnrollment(Base):
    """
    Records a user's decision to enroll (or not) a specific FlexibleResource
    into a VTN program.
    """
    __tablename__ = "vtn_program_enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(UUID(as_uuid=True), ForeignKey("vtn_programs.id"), nullable=False, index=True)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("flexible_resources.id"), nullable=False, index=True)

    status = Column(
        String(50),
        default=VTNProgramEnrollmentStatus.NOT_ENROLLED.value,
        nullable=False,
    )
    requested_at = Column(DateTime)
    enrolled_at = Column(DateTime)
    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    program = relationship("VTNProgram", back_populates="enrollments")
    resource = relationship("FlexibleResource")

    def __repr__(self):
        return (
            f"<VTNProgramEnrollment(program='{self.program_id}', "
            f"resource='{self.resource_id}', status='{self.status}')>"
        )


class OptimizationRun(Base):
    """
    Records each optimization run (backtest or forecast) with its parameters and results.
    """
    __tablename__ = "optimization_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_group_id = Column(UUID(as_uuid=True), ForeignKey("asset_groups.id"), nullable=True, index=True)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("flexible_resources.id"), nullable=True, index=True)

    run_type = Column(String(50), nullable=False)   # "backtest" | "forecast"
    price_area = Column(String(20))
    grid_company = Column(String(200))

    # Time window
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Battery / DER parameters (snapshot at run time)
    battery_capacity_kwh = Column(Float)
    battery_max_charge_kw = Column(Float)
    battery_max_discharge_kw = Column(Float)
    battery_efficiency = Column(Float, default=0.95)
    initial_soc = Column(Float, default=0.5)        # 0..1

    # Results summary
    status = Column(String(50), default="pending")   # pending | running | completed | failed
    objective_value = Column(Float)                  # e.g. total NOK earnings
    total_cycles = Column(Float)
    solver_used = Column(String(50))
    solve_time_s = Column(Float)
    error_message = Column(Text)

    # JSON payload of full results (schedule, prices used, etc.)
    result_json = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)

    schedules = relationship("OptimizationSchedule", back_populates="run", cascade="all, delete-orphan",
                             order_by="OptimizationSchedule.period_start")

    def __repr__(self):
        return f"<OptimizationRun(id='{self.id}', type='{self.run_type}', status='{self.status}')>"


class OptimizationSchedule(Base):
    """
    Per-interval dispatch schedule produced by an OptimizationRun.
    """
    __tablename__ = "optimization_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("optimization_runs.id"), nullable=False, index=True)

    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)

    # Dispatch decision
    charge_kw = Column(Float, default=0.0)      # positive = charging
    discharge_kw = Column(Float, default=0.0)   # positive = discharging
    net_power_kw = Column(Float)                # discharge - charge (positive = export)
    soc_kwh = Column(Float)                     # state of charge at end of interval

    # Market values for this interval
    spot_price_nok_mwh = Column(Float)
    grid_tariff_nok_kwh = Column(Float)
    total_cost_nok = Column(Float)
    total_revenue_nok = Column(Float)
    net_earnings_nok = Column(Float)

    run = relationship("OptimizationRun", back_populates="schedules")

    def __repr__(self):
        return f"<OptimizationSchedule(run='{self.run_id}', start='{self.period_start}', net={self.net_power_kw})>"


class VTNEvent(Base):
    """
    OpenADR events received from the VTN.
    Tracks demand response events and their execution.
    """
    __tablename__ = "vtn_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("flexible_resources.id"), nullable=False, index=True)

    # Event identification
    vtn_event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100))  # e.g., 'SIMPLE', 'LOAD_CONTROL'

    # Event timing
    event_start = Column(DateTime, nullable=False)
    event_end = Column(DateTime, nullable=False)
    notification_time = Column(DateTime, nullable=False)

    # Event details
    signal_name = Column(String(100))  # e.g., 'SIMPLE'
    signal_type = Column(String(100))
    target_value = Column(Float)  # Target setpoint
    current_value = Column(Float)  # Baseline value

    # Event status
    opt_status = Column(String(50))  # optIn, optOut
    execution_status = Column(String(50))  # pending, active, completed, cancelled, failed

    # Response tracking
    response_sent = Column(Boolean, default=False)
    response_time = Column(DateTime)
    execution_started = Column(DateTime)
    execution_completed = Column(DateTime)

    # Metadata
    raw_event_data = Column(Text)  # JSON of original event
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    resource = relationship("FlexibleResource")

    def __repr__(self):
        return f"<VTNEvent(vtn_event_id='{self.vtn_event_id}', resource_id='{self.resource_id}', status='{self.execution_status}')>"
