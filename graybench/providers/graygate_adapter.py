import time
import requests
import json
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime

from graybench.providers.base import (
    ProviderAdapter,
    GenerationRequest,
    GenerationResult,
    TokenUsage,
    ProviderError,
    RateLimitError,
    AuthenticationError,
)

# Dummy pricing since we're running locally/via another provider
GRAYGATE_PRICING = {
    "graygate-default": {"input": 0.0, "output": 0.0},
}


class GrayGateAdapter(ProviderAdapter):
    """
    Adapter for the GrayGate API.
    
    This adapter communicates with a locally running GrayGate server.
    """
    
    provider_name = "graygate"
    supported_models = ["graygate-default", "gemini-3-pro-preview", "gemini-3-flash-preview"]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = "http://localhost:8000",
        **kwargs
    ):
        super().__init__(api_key, base_url, **kwargs)
        self.api_key = api_key  # This will be the Bearer token for runs
        self.base_url = base_url.rstrip("/")
        
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate a solution using GrayGate.
        
        This triggers a new run, waits for it to complete, and returns the solution.
        """
        start_time = self._time_request()
        
        # 1. Create Run
        try:
            run_id = self._create_run(request.prompt)
        except Exception as e:
            return self._handle_error(e, request.model, start_time)
            
        # 2. Poll for completion
        try:
            result = self._poll_run(run_id)
        except Exception as e:
            # Try to cancel if polling fails
            try:
                self._cancel_run(run_id)
            except:
                pass
            return self._handle_error(e, request.model, start_time)
            
        # 3. Extract solution
        completion_text = self._extract_solution_from_result(result)
        
        # 4. Calculate usage (if available in result, otherwise estimate)
        # GrayGate result structure needs to be checked for usage info
        # For now, we'll estimate or leave as 200/200
        usage = TokenUsage(
            input_tokens=200,
            output_tokens=200,
            total_tokens=400
        )
        
        latency_ms = self._calculate_latency_ms(start_time)
        
        return GenerationResult(
            provider=self.provider_name,
            model=request.model,
            prompt_text=request.prompt,
            completion_text=completion_text,
            usage=usage,
            cost_usd=0.0,
            latency_ms=latency_ms,
            raw_response=result,
        )
        
    def _create_run(self, prompt: str) -> str:
        """Create a new run and return its ID."""
        url = f"{self.base_url}/v1/runs"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # GrayGate expects: {"input": {"prompt": "..."}}
        payload = {
            "input": {
                "prompt": prompt
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 401:
            raise AuthenticationError("Invalid API key", self.provider_name)
        elif response.status_code != 200:
            raise ProviderError(f"Failed to create run: {response.text}", self.provider_name)
            
        data = response.json()
        return data.get("id") or data.get("run_id")
        
    def _poll_run(self, run_id: str, timeout: int = 1800, interval: int = 2) -> Dict[str, Any]:
        """Poll run status until success or failure."""
        url = f"{self.base_url}/v1/runs/{run_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        start_wait = time.time()
        
        while time.time() - start_wait < timeout:
            try:
                response = requests.get(url, headers=headers, timeout=10)
            except requests.RequestException:
                time.sleep(interval)
                continue
            
            if response.status_code != 200:
                # Retry on transient network errors, but fail on 4xx
                if 400 <= response.status_code < 500:
                     raise ProviderError(f"Failed to get run status: {response.text}", self.provider_name)
                time.sleep(interval)
                continue
                
            data = response.json()
            status = data.get("status")
            
            if status == "succeeded":
                # Fetch full result
                return self._get_run_result(run_id)
            elif status == "failed":
                error_data = data.get("error")
                error_msg = "Unknown error"
                if isinstance(error_data, dict):
                     error_msg = error_data.get("message", "Unknown error")
                elif isinstance(error_data, str):
                     error_msg = error_data
                raise ProviderError(f"Run failed: {error_msg}", self.provider_name)
            elif status == "cancelled":
                raise ProviderError("Run was cancelled", self.provider_name)
                
            time.sleep(interval)
            
        raise TimeoutError("Run timed out while polling")
        
    def _get_run_result(self, run_id: str) -> Dict[str, Any]:
        """Fetch the final result of the run."""
        url = f"{self.base_url}/v1/runs/{run_id}/result"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                raise ProviderError(f"Failed to get run result: {response.text}", self.provider_name)
            return response.json()
        except requests.RequestException as e:
            raise ProviderError(f"Network error getting result: {str(e)}", self.provider_name)
        
    def _cancel_run(self, run_id: str):
        """Cancel the run."""
        url = f"{self.base_url}/v1/runs/{run_id}/cancel"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        requests.post(url, headers=headers, timeout=10)

    def _extract_solution_from_result(self, result: Dict[str, Any]) -> str:
        """
        Extract the solution code from the run result.
        
        Expected structure:
        {
            "output": {
                "code": "..."
            }
        }
        """
        output = result.get("output", {})
        if isinstance(output, dict):
            return output.get("code", "")
        return ""
        
    def calculate_cost(self, usage: TokenUsage, model: str) -> float:
        return 0.0

    def _handle_error(self, e: Exception, model: str, start_time: float) -> GenerationResult:
        """Handle exceptions and return a failed GenerationResult."""
        error_msg = str(e)
        latency_ms = self._calculate_latency_ms(start_time)
        
        return GenerationResult(
            provider=self.provider_name,
            model=model,
            prompt_text="",
            completion_text="",
            usage=TokenUsage(),
            cost_usd=0.0,
            latency_ms=latency_ms,
            error=error_msg
        )
