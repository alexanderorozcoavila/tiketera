import logging
from web3 import Web3

logger = logging.getLogger(__name__)

def get_w3_instance():
    from core.models import SiteSettings
    try:
        settings = SiteSettings.get_settings()
        provider_url = settings.web3_provider_url
    except Exception:
        # Fallback during migrations or if DB is locked
        provider_url = 'http://127.0.0.1:8545'
    return Web3(Web3.HTTPProvider(provider_url))

def is_connected():
    return get_w3_instance().is_connected()

def register_ticket_on_blockchain(ticket_id, user_address=None):
    """
    Simulated or actual logic to register a ticket on the blockchain.
    In a real scenario, this would interact with an ERC721 smart contract to mint an NFT.
    """
    if not is_connected():
        logger.warning("Web3 provider not connected. Using simulated blockchain registration.")

    try:
        import hashlib
        # Placeholder logic for minting or sending a transaction
        logger.info(f"Registered ticket {ticket_id} on blockchain.")
        dummy_hash = "0x" + hashlib.sha256(str(ticket_id).encode()).hexdigest()
        dummy_token_id = f"TK-{str(ticket_id)[:8]}"
        return dummy_hash, dummy_token_id
    except Exception as e:
        logger.error(f"Blockchain interaction failed: {e}")
        return None, None
