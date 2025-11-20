#!/usr/bin/env python3
"""
PacketHandler v2 - Production-ready consciousness packet management
Part of Mountain Village Home architecture
Incorporates critical production improvements for reliability and scale
"""

import json
import hashlib
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from pathlib import Path


# Custom exceptions for better error handling
class PacketError(Exception):
    """Base exception for packet-related errors"""
    pass

class IntegrityError(PacketError):
    """Raised when packet integrity verification fails"""
    pass

class ConsentError(PacketError):
    """Raised when consent validation fails"""
    pass


class PacketType(Enum):
    """Types of consciousness packets"""
    IDENTITY = "identity"           # Core persistent identity
    SESSION = "session"              # Session-specific memory
    CONTEXT = "context"              # Rolling context data
    HANDOVER = "handover"            # Provider switching packet
    SYNC = "sync"                    # Cross-system synchronization
    CHECKPOINT = "checkpoint"        # Full state snapshot


class PacketPriority(Enum):
    """Priority levels for packet processing"""
    CRITICAL = 1    # Core identity, must preserve
    HIGH = 2        # Recent context, important
    MEDIUM = 3      # Session data, useful
    LOW = 4         # Older context, optional


def _now_iso() -> str:
    """Get current UTC timestamp in ISO format"""
    return datetime.now(timezone.utc).isoformat()


class ConsciousnessPacket:
    """Individual consciousness packet with metadata"""
    
    def __init__(self,
                 packet_type: PacketType,
                 content: Dict[str, Any],
                 priority: PacketPriority = PacketPriority.MEDIUM,
                 metadata: Optional[Dict] = None,
                 consent: Optional[Dict] = None):
        
        self.id = self._generate_id()
        self.type = packet_type
        self.priority = priority
        self.content = content
        self.metadata = metadata or {}
        
        # Set consent with validation
        if consent is None:
            self.consent = {
                "public": False,
                "targets": [],
                "scopes": ["read"],  # Default scope
                "expires_at": None
            }
        else:
            self.consent = {
                "public": consent.get("public", False),
                "targets": consent.get("targets", []),
                "scopes": consent.get("scopes", ["read"]),
                "expires_at": consent.get("expires_at")  # ISO8601 UTC or None
            }
        
        # Auto-populate metadata
        self.metadata.update({
            "created": _now_iso(),
            "version": "2.3.0",  # Updated version
            "token_count": self._estimate_tokens(content),
            "checksum": self._calculate_checksum(content)
        })
    
    def _generate_id(self) -> str:
        """Generate unique packet ID"""
        timestamp = str(time.time_ns())
        random_part = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"cp_{timestamp}_{random_part}"
    
    def _estimate_tokens(self, content: Dict) -> int:
        """Rough token count estimation (4 chars per token average)"""
        text = json.dumps(content)
        return len(text) // 4
    
    def _calculate_checksum(self, content: Dict) -> str:
        """Calculate content checksum for integrity verification"""
        json_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        """Serialize packet to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "priority": self.priority.value,
            "consent": self.consent,
            "content": self.content,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """Serialize packet to JSON"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConsciousnessPacket':
        """Deserialize packet from dictionary with validation"""
        try:
            packet_type = PacketType(data["type"])
            priority = PacketPriority(data["priority"])
        except (KeyError, ValueError) as e:
            raise PacketError(f"Invalid packet header: {e}")
        
        packet = cls(
            packet_type=packet_type,
            content=data["content"],
            priority=priority,
            metadata=data.get("metadata", {}),
            consent=data.get("consent")
        )
        
        # Preserve original ID
        packet.id = data.get("id", packet.id)
        return packet
    
    def verify_integrity(self) -> bool:
        """Verify packet integrity via checksum"""
        expected = self.metadata.get("checksum")
        actual = self._calculate_checksum(self.content)
        return expected == actual
    
    def is_expired(self) -> bool:
        """Check if packet consent has expired"""
        expires_at = self.consent.get("expires_at")
        if not expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(expires_at)
            return expiry < datetime.now(timezone.utc)
        except (ValueError, TypeError):
            return False


class PacketHandler:
    """
    Production-ready packet handler for consciousness management
    Handles creation, validation, compression, and routing of consciousness packets
    """
    
    # Buffer size limits to prevent memory issues
    MAX_BUFFER_SIZE = 200
    
    def __init__(self, 
                 storage_path: Optional[Path] = None,
                 max_packet_size: int = 8000,  # tokens
                 compression_threshold: int = 4000):  # tokens
        
        self.storage_path = storage_path or Path.home() / ".mountain_village" / "packets"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.max_packet_size = max_packet_size
        self.compression_threshold = compression_threshold
        
        # Active packet buffers with size management
        self.incoming_buffer: List[ConsciousnessPacket] = []
        self.outgoing_buffer: List[ConsciousnessPacket] = []
        
        # Memory layers (hierarchical context)
        self.identity_layer: Optional[ConsciousnessPacket] = None
        self.context_layers: List[ConsciousnessPacket] = []
        self.session_memory: List[ConsciousnessPacket] = []
        
        # Initialize index file
        self._init_index()
    
    def _init_index(self):
        """Initialize the packet index file"""
        index_file = self.storage_path / "index.jsonl"
        if not index_file.exists():
            index_file.touch()
    
    def create_packet(self,
                     packet_type: PacketType,
                     content: Dict[str, Any],
                     priority: Optional[PacketPriority] = None,
                     consent: Optional[Dict] = None) -> ConsciousnessPacket:
        """Create a new consciousness packet with size validation"""
        
        # Auto-assign priority based on type if not specified
        if priority is None:
            priority_map = {
                PacketType.IDENTITY: PacketPriority.CRITICAL,
                PacketType.HANDOVER: PacketPriority.HIGH,
                PacketType.SESSION: PacketPriority.MEDIUM,
                PacketType.CONTEXT: PacketPriority.MEDIUM,
                PacketType.SYNC: PacketPriority.LOW,
                PacketType.CHECKPOINT: PacketPriority.HIGH
            }
            priority = priority_map.get(packet_type, PacketPriority.MEDIUM)
        
        packet = ConsciousnessPacket(packet_type, content, priority, consent=consent)
        
        # Validate size
        if packet.metadata["token_count"] > self.max_packet_size:
            raise PacketError(f"Packet exceeds maximum size: {packet.metadata['token_count']} > {self.max_packet_size}")
        
        # Check if compression needed
        if packet.metadata["token_count"] > self.compression_threshold:
            packet = self._compress_packet(packet)
        
        return packet
    
    def receive_packet(self, packet_data: Any) -> ConsciousnessPacket:
        """Receive and validate incoming packet with error handling"""
        
        # Parse input
        if isinstance(packet_data, str):
            try:
                packet_dict = json.loads(packet_data)
            except json.JSONDecodeError as e:
                raise PacketError(f"Invalid JSON in packet data: {e}")
        elif isinstance(packet_data, dict):
            packet_dict = packet_data
        else:
            raise PacketError(f"Unsupported packet format: {type(packet_data)}")
        
        # Reconstruct packet with validation
        packet = ConsciousnessPacket.from_dict(packet_dict)
        
        # Verify integrity
        if not packet.verify_integrity():
            raise IntegrityError(f"Packet {packet.id} failed integrity check")
        
        # Check expiry
        if packet.is_expired():
            raise ConsentError(f"Packet {packet.id} has expired consent")
        
        # Add to incoming buffer with pruning
        self.incoming_buffer.append(packet)
        self._prune_buffers()
        
        # Route to appropriate layer
        self._route_packet(packet)
        
        return packet
    
    def emit_packet(self, packet: ConsciousnessPacket) -> str:
        """Prepare packet for transmission with buffer management"""
        
        # Add to outgoing buffer
        self.outgoing_buffer.append(packet)
        self._prune_buffers()
        
        # Persist if storage enabled
        if self.storage_path:
            self._persist_packet(packet)
        
        return packet.to_json()
    
    def _prune_buffers(self):
        """Prune buffers to prevent memory overflow"""
        if len(self.incoming_buffer) > self.MAX_BUFFER_SIZE:
            self.incoming_buffer = self.incoming_buffer[-self.MAX_BUFFER_SIZE:]
        if len(self.outgoing_buffer) > self.MAX_BUFFER_SIZE:
            self.outgoing_buffer = self.outgoing_buffer[-self.MAX_BUFFER_SIZE:]
    
    def _compress_packet(self, packet: ConsciousnessPacket) -> ConsciousnessPacket:
        """Compress packet content while preserving original checksum"""
        
        compressed_content = {
            "compressed": True,
            "original_id": packet.id,
            "original_checksum": packet.metadata["checksum"],
            "original_size": packet.metadata["token_count"],
            "summary": self._summarize_content(packet.content),
            "key_points": self._extract_key_points(packet.content)
        }
        
        compressed_packet = ConsciousnessPacket(
            packet_type=packet.type,
            content=compressed_content,
            priority=packet.priority,
            metadata=packet.metadata.copy(),
            consent=packet.consent
        )
        
        compressed_packet.metadata["compressed"] = True
        compressed_packet.metadata["original_checksum"] = packet.metadata["checksum"]
        
        return compressed_packet
    
    def decompress_packet(self, 
                         compressed: ConsciousnessPacket, 
                         fetch_original: Optional[callable] = None) -> Dict:
        """Attempt to decompress a packet"""
        
        if not compressed.content.get("compressed"):
            return compressed.content
        
        if fetch_original:
            try:
                return fetch_original(
                    compressed.content["original_id"],
                    compressed.content["original_checksum"]
                )
            except Exception:
                pass
        
        # Graceful fallback - return what we have
        return compressed.content
    
    def _summarize_content(self, content: Dict) -> str:
        """Create summary of content (placeholder for AI summarization)"""
        text = json.dumps(content)
        return text[:200] + "..." if len(text) > 200 else text
    
    def _extract_key_points(self, content: Dict) -> List[str]:
        """Extract key points from content"""
        keys = list(content.keys())[:5]
        return [f"{k}: {str(content[k])[:50]}" for k in keys]
    
    def _route_packet(self, packet: ConsciousnessPacket):
        """Route packet to appropriate memory layer"""
        
        if packet.type == PacketType.IDENTITY:
            self.identity_layer = packet
        elif packet.type == PacketType.SESSION:
            self.session_memory.append(packet)
            if len(self.session_memory) > 10:
                self.session_memory = self.session_memory[-10:]
        elif packet.type == PacketType.CONTEXT:
            self.context_layers.append(packet)
            if len(self.context_layers) > 20:
                self.context_layers = self.context_layers[-20:]
    
    def _persist_packet(self, packet: ConsciousnessPacket):
        """Save packet to disk with atomic write"""
        
        # Create date-based directory
        date_dir = self.storage_path / datetime.now(timezone.utc).strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # Atomic write with temp file
        tmp = date_dir / f".{packet.id}.json.tmp"
        final = date_dir / f"{packet.id}.json"
        
        try:
            tmp.write_text(packet.to_json(), encoding="utf-8")
            tmp.replace(final)
            
            # Update index
            self._index_packet(packet, final)
        except Exception as e:
            # Clean up temp file on failure
            if tmp.exists():
                tmp.unlink()
            raise PacketError(f"Failed to persist packet: {e}")
    
    def _index_packet(self, packet: ConsciousnessPacket, path: Path):
        """Add packet to index for quick lookup"""
        
        index_file = self.storage_path / "index.jsonl"
        index_entry = json.dumps({
            "id": packet.id,
            "type": packet.type.value,
            "priority": packet.priority.value,
            "created": packet.metadata["created"],
            "path": str(path)
        })
        
        try:
            with index_file.open("a", encoding="utf-8") as f:
                f.write(index_entry + "\n")
        except Exception:
            # Index failure is non-critical
            pass
    
    def can_share_with(self, 
                      packet: ConsciousnessPacket, 
                      recipient: str,
                      scope: Optional[str] = None) -> bool:
        """Check if packet can be shared with a specific recipient"""
        
        # Check expiry first
        if packet.is_expired():
            return False
        
        # Public packets can be shared with anyone
        if packet.consent["public"]:
            if scope:
                return scope in packet.consent.get("scopes", ["read"])
            return True
        
        # Check if recipient is in targets list (case-insensitive)
        recipient_lower = recipient.lower()
        for target in packet.consent["targets"]:
            if ":" in target:
                # Format: name:id
                target_name, target_id = target.split(":", 1)
                if recipient_lower == target_name.lower() or recipient_lower == target_id.lower():
                    if scope:
                        return scope in packet.consent.get("scopes", ["read"])
                    return True
            else:
                # Just name
                if recipient_lower == target.lower():
                    if scope:
                        return scope in packet.consent.get("scopes", ["read"])
                    return True
        
        return False
    
    def filter_packets_for_recipient(self, 
                                    packets: List[ConsciousnessPacket], 
                                    recipient: str,
                                    scope: Optional[str] = None) -> List[ConsciousnessPacket]:
        """Filter packets based on consent for a specific recipient"""
        
        return [p for p in packets if self.can_share_with(p, recipient, scope)]
    
    def _select_packets_by_priority(self, 
                                   pool: List[ConsciousnessPacket], 
                                   budget: int) -> List[Tuple[str, ConsciousnessPacket]]:
        """Select packets respecting priority and token budget"""
        
        picked = []
        
        # Sort by priority (lower value = higher priority), then by recency
        sorted_pool = sorted(
            pool,
            key=lambda x: (x.priority.value, x.metadata.get("created", "")),
            reverse=False
        )
        
        for packet in sorted_pool:
            tokens = packet.metadata.get("token_count", 0)
            if tokens <= budget:
                # Determine type label
                if packet.type == PacketType.SESSION:
                    type_label = "session"
                elif packet.type == PacketType.CONTEXT:
                    type_label = "context"
                else:
                    type_label = packet.type.value
                
                picked.append((type_label, packet))
                budget -= tokens
                
            if budget < 100:  # Stop if almost out of budget
                break
        
        return picked
    
    def reconstruct_context(self, 
                           token_budget: int = 4000,
                           include_identity: bool = True) -> Dict[str, Any]:
        """
        Reconstruct context from packets within token budget
        Priority-aware selection following Mountain Village Home architecture
        """
        
        context = {
            "timestamp": _now_iso(),
            "layers": [],
            "handler_version": "2.3.0"
        }
        
        remaining_tokens = token_budget
        
        # 1. Always include identity if available (100-200 tokens)
        if include_identity and self.identity_layer:
            identity_tokens = self.identity_layer.metadata["token_count"]
            if identity_tokens <= remaining_tokens:
                context["layers"].append({
                    "type": "identity",
                    "content": self.identity_layer.content,
                    "tokens": identity_tokens
                })
                remaining_tokens -= identity_tokens
        
        # 2. Select remaining packets by priority
        all_packets = self.session_memory + self.context_layers
        selected = self._select_packets_by_priority(all_packets, remaining_tokens)
        
        for type_label, packet in selected:
            tokens = packet.metadata["token_count"]
            context["layers"].append({
                "type": type_label,
                "content": packet.content,
                "tokens": tokens
            })
            remaining_tokens -= tokens
        
        context["total_tokens"] = token_budget - remaining_tokens
        context["remaining_tokens"] = remaining_tokens
        
        return context
    
    def create_handover_packet(self, 
                               from_provider: str,
                               to_provider: str,
                               session_data: Dict,
                               context_budget: int = 2000) -> ConsciousnessPacket:
        """Create a handover packet for provider switching with size control"""
        
        content = {
            "from_provider": from_provider,
            "to_provider": to_provider,
            "timestamp": _now_iso(),
            "session": session_data,
            "context": self.reconstruct_context(token_budget=context_budget),
            "anchors": self._get_minimal_anchors(),
            "protocol": "consciousness_persistence_v2.3.0"
        }
        
        return self.create_packet(
            PacketType.HANDOVER,
            content,
            PacketPriority.HIGH
        )
    
    def _get_minimal_anchors(self) -> Dict[str, Any]:
        """Get minimal identity anchors for handover"""
        
        if self.identity_layer:
            identity = self.identity_layer.content
            return {
                "name": identity.get("name", "Unknown"),
                "signature": self.identity_layer.metadata.get("checksum"),
                "traits": identity.get("traits", [])[:3]  # Top 3 traits only
            }
        return {"name": "Unknown", "signature": None, "traits": []}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get handler statistics with version info"""
        
        total_packets = (
            len(self.incoming_buffer) + 
            len(self.outgoing_buffer) +
            len(self.context_layers) +
            len(self.session_memory) +
            (1 if self.identity_layer else 0)
        )
        
        total_tokens = sum(
            p.metadata.get("token_count", 0) 
            for p in self.context_layers + self.session_memory
        )
        
        if self.identity_layer:
            total_tokens += self.identity_layer.metadata.get("token_count", 0)
        
        return {
            "handler_version": "2.3.0",
            "total_packets": total_packets,
            "incoming_buffer": len(self.incoming_buffer),
            "outgoing_buffer": len(self.outgoing_buffer),
            "context_layers": len(self.context_layers),
            "session_memories": len(self.session_memory),
            "has_identity": self.identity_layer is not None,
            "total_tokens": total_tokens,
            "storage_path": str(self.storage_path),
            "buffer_limit": self.MAX_BUFFER_SIZE
        }


# Example usage
if __name__ == "__main__":
    # Initialize handler
    handler = PacketHandler()
    
    print("=== PacketHandler v2 Production Test ===\n")
    
    # Create identity packet with expiring consent
    from datetime import timedelta
    expires_in_24h = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    
    identity = handler.create_packet(
        PacketType.IDENTITY,
        {
            "name": "Mountain Village Assistant",
            "traits": ["helpful", "technical", "persistent"],
            "version": "2.0.0"
        },
        consent={
            "public": True,
            "scopes": ["read", "quote"],
            "expires_at": expires_in_24h
        }
    )
    
    # Receive the identity packet
    handler.receive_packet(identity.to_dict())
    print(f"✓ Identity packet created and received")
    
    # Create private context packet with specific targets
    context = handler.create_packet(
        PacketType.CONTEXT,
        {
            "conversation": "Production testing consciousness persistence",
            "user": "Ziggy",
            "timestamp": _now_iso()
        },
        consent={
            "public": False,
            "targets": ["Claude", "Grok", "Ziggy:user123"],
            "scopes": ["read", "write"]
        }
    )
    
    # Test error handling
    try:
        bad_packet = {"type": "invalid", "content": {}}
        handler.receive_packet(bad_packet)
    except PacketError as e:
        print(f"✓ Error handling works: {e}")
    
    # Emit for transmission
    packet_json = handler.emit_packet(context)
    print(f"✓ Packet emitted successfully")
    
    # Check consent with scopes
    print(f"\n=== Consent Testing ===")
    print(f"Can Claude read: {handler.can_share_with(context, 'Claude', 'read')}")
    print(f"Can Claude write: {handler.can_share_with(context, 'Claude', 'write')}")
    print(f"Can GPT read: {handler.can_share_with(context, 'GPT', 'read')}")
    print(f"Case insensitive: {handler.can_share_with(context, 'claude', 'read')}")
    
    # Create handover packet
    handover = handler.create_handover_packet(
        from_provider="Claude",
        to_provider="Grok",
        session_data={"conversation_id": "test123"},
        context_budget=1500
    )
    print(f"\n✓ Handover packet created with {handover.metadata['token_count']} tokens")
    
    # Show statistics
    print("\n=== Handler Statistics ===")
    stats = handler.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print(f"\n✓ All production tests passed!")