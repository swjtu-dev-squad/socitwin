#!/bin/bash
# Quick test runner script

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
PLATFORM="twitter"
AGENT_COUNT=5
MAX_STEPS=10
TOPIC="2042552568010936455"  # Singapore's elite leader path vs UK's political rise
MEMORY_MODE="action_v1"
MAX_TOKENS=1024
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        --agent-count)
            AGENT_COUNT="$2"
            shift 2
            ;;
        --max-steps)
            MAX_STEPS="$2"
            shift 2
            ;;
        --topic)
            TOPIC="$2"
            shift 2
            ;;
        --memory-mode)
            MEMORY_MODE="$2"
            shift 2
            ;;
        --max-tokens)
            MAX_TOKENS="$2"
            shift 2
            ;;
        --quick)
            MAX_STEPS=3
            AGENT_COUNT=3
            shift
            ;;
        --full)
            MAX_STEPS=50
            AGENT_COUNT=10
            shift
            ;;
        -h|--help)
            echo "Usage: ./run_tests.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --platform PLATFORM       Platform (twitter/reddit) [default: twitter]"
            echo "  --agent-count COUNT       Number of agents [default: 5]"
            echo "  --max-steps STEPS         Number of steps [default: 10]"
            echo "  --topic TOPIC             Topic ID [default: climate_change_debate]"
            echo "  --memory-mode MODE        Memory route (upstream/action_v1) [default: action_v1]"
            echo "  --max-tokens TOKENS       LLM generation max tokens [default: 1024]"
            echo "  --quick                   Quick test (3 steps, 3 agents)"
            echo "  --full                    Full test (50 steps, 10 agents)"
            echo "  -h, --help                Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./run_tests.sh --quick"
            echo "  ./run_tests.sh --agent-count 10 --max-steps 20 --topic tech_ai_regulation"
            echo "  ./run_tests.sh --platform reddit --topic crypto_discussion"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Check if server is running
echo -e "${YELLOW}Checking if server is running...${NC}"
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${RED}Error: Server is not running!${NC}"
    echo "Please start the server first:"
    echo "  cd backend"
    echo "  source .venv/bin/activate"
    echo "  uvicorn main:app --reload --host 0.0.0.0 --port 8000"
    exit 1
fi

echo -e "${GREEN}✓ Server is running${NC}"
echo ""

# Run the test
echo -e "${YELLOW}Running e2e test with:${NC}"
echo "  Platform: $PLATFORM"
echo "  Agent Count: $AGENT_COUNT"
echo "  Max Steps: $MAX_STEPS"
echo "  Topic: $TOPIC"
echo "  Memory Mode: $MEMORY_MODE"
echo "  Max Tokens: $MAX_TOKENS"
echo ""

python "$SCRIPT_DIR/e2e_simulation_test.py" \
    --platform "$PLATFORM" \
    --agent-count "$AGENT_COUNT" \
    --max-steps "$MAX_STEPS" \
    --topic "$TOPIC" \
    --memory-mode "$MEMORY_MODE" \
    --max-tokens "$MAX_TOKENS"

exit $?
