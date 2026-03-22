# Workshop UI Package

This package contains the pre-built UI components for the "Everyday Productivity Accelerators" workshop.

## Quick Start

1. **Extract the package:**
   ```bash
   unzip workshop-ui-package.zip
   cd ui
   ```

2. **Backend Setup:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Frontend Setup:**
   ```bash
   cd ../frontend
   npm install
   ```

4. **Start the Application:**
   ```bash
   cd ..
   ./start.sh
   ```

5. **Access the Application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000

## Workshop Structure

- `backend/` - Python FastAPI backend with Strands Agents
- `frontend/` - React frontend application
- `start.sh` - Convenience script to start both services

## Requirements

- Python 3.11+
- Node.js 18+
- AWS credentials configured for Bedrock access

## AWS Services Used

This workshop makes use of the following AWS services:

| Service | Purpose |
|---|---|
| **Amazon Bedrock** | AI model inference (Nova Pro, Claude Sonnet) |
| **Amazon Bedrock AgentCore** | Managed runtime for deploying and hosting MCP servers as scalable agents |
| **Strands Agents** | Open-source AWS agent framework used to build AI agents backed by Bedrock models |
| **Amazon CloudWatch** | Observability and logging via AWS OpenTelemetry instrumentation |
| **Amazon ECR** | Elastic Container Registry — stores Docker images for AgentCore deployments |
| **AWS CodeBuild** | Builds and packages container images for deployment |
| **Amazon S3** | Object storage used for workshop artifacts and package distribution |
| **AWS IAM** | Identity and Access Management — SigV4 authentication for secure MCP server access |
| **AWS Systems Manager (SSM) Parameter Store** | Stores and retrieves configuration values such as AgentCore runtime ARNs |

## Support

If you encounter issues during the workshop, please ask your instructor for assistance.

---
*Built for AWS Workshop*
