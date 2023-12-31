from src.utils import root_directory

# Note, the use of keywords List is an attempt at filtering YouTube videos by name content to reduce noise
KEYWORDS_TO_INCLUDE = ['order flow', 'orderflow', 'transaction', 'mev', 'ordering', 'sgx', 'intent', 'dex', 'front-running', 'arbitrage', 'back-running',
            'maximal extractable value', 'trading games', 'timing games', 'arbitrage games', 'timing', 'on-chain games', 'pepc', 'proposer', 'builder', 'barnabe',
            'fees', 'pbs', '4337', 'account abstraction', 'boost', 'defi', 'uniswap', 'hook', 'anoma', 'espresso',
            'suave', 'flashbots', 'celestia', 'gas war', 'hasu', 'dan robinson', 'jon charbonneau', 'robert miller', 'paradigm',
            'altlayer', 'tarun', 'modular summit', 'latency', 'market design', 'searcher', 'staking', 'pre-merge', 'post-merge',
            'liquid staking', 'crediblecommitments', 'tee', 'market microstructure', 'rollups', 'uniswap', '1inch',
            'cow', 'censorship', 'liquidity', 'censorship', 'ofa', 'pfof', 'payment for order flow', 'decentralisation', 'decentralization',
            'erc', 'eip', 'auction', 'daian', 'mechanism design', 'Price-of-Anarchy', 'protocol economics', 'stephane gosselin', 'su zhu', 'pools', 'censorship',
            '1559', 'BFT', 'selfish mining', 'vickrey auctions', 'Alex Nezlobin', 'Jason Milionis', "How They Solved Ethereum's Critical Flaw"]

# , 'smart contract', 'eth global',  'evm',  #  'vitalik', 'buterin', bridge',
KEYWORDS_TO_EXCLUDE = ['DAO', 'NFTs', 'joke', 'jokes', 'short', 'shorts', '#', 'gensler', 'sec', 'T-Shirt', "New year's breathing exercise",
                       'From lifespan to healthspan (1)', 'On promoting healthspan and quality of life (2)']

YOUTUBE_VIDEOS_CSV_FILE_PATH = f"{root_directory()}/data/links/youtube/youtube_videos.csv"
