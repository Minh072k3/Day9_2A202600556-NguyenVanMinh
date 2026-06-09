import './style.css'

const chatForm = document.getElementById('chatForm');
const userInput = document.getElementById('userInput');
const chatContainer = document.getElementById('chatContainer');
const sendBtn = document.getElementById('sendBtn');

// Helper sleep function to simulate latency
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// UI Update Functions
function setAgentStatus(agentId, statusText, statusClass) {
  const card = document.getElementById(`agent-${agentId}`);
  if (!card) return;
  
  const statusEl = card.querySelector('.status');
  
  card.className = `agent-card ${statusClass === 'active' ? 'active' : ''}`;
  statusEl.className = `status ${statusClass}`;
  statusEl.textContent = statusText;
}

function appendMessage(sender, text, isHtml = false) {
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${sender}`;
  
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = sender === 'user' ? '👤' : '🤖';
  
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  
  if (isHtml) {
    bubble.innerHTML = text;
  } else {
    bubble.textContent = text;
  }
  
  msgDiv.appendChild(avatar);
  msgDiv.appendChild(bubble);
  
  chatContainer.appendChild(msgDiv);
  chatContainer.scrollTop = chatContainer.scrollHeight;
  return msgDiv;
}

function appendLoading() {
  const msgDiv = document.createElement('div');
  msgDiv.className = 'message system loading';
  msgDiv.id = 'loadingMessage';
  
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = '🤖';
  
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = `
    Đang xử lý
    <div class="dot"></div>
    <div class="dot"></div>
    <div class="dot"></div>
  `;
  
  msgDiv.appendChild(avatar);
  msgDiv.appendChild(bubble);
  
  chatContainer.appendChild(msgDiv);
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function removeLoading() {
  const loading = document.getElementById('loadingMessage');
  if (loading) loading.remove();
}

// Reset all agents to idle
function resetAgents() {
  ['supervisor', 'law', 'tax', 'privacy', 'synthesizer'].forEach(agent => {
    setAgentStatus(agent, 'Idle', 'idle');
  });
}

// Simulated Multi-Agent Pipeline
async function simulateAgentPipeline(question) {
  const questionLower = question.toLowerCase();
  
  // 1. Supervisor Phase
  setAgentStatus('supervisor', 'Analyzing...', 'active');
  await sleep(1000);
  
  const needsLaw = true; // Always need law
  const needsTax = questionLower.includes('thuế') || questionLower.includes('tax');
  const needsPrivacy = questionLower.includes('dữ liệu') || questionLower.includes('privacy');
  
  setAgentStatus('supervisor', 'Delegated', 'done');
  
  // 2. Parallel Workers Phase
  const workerPromises = [];
  
  // Law Worker
  setAgentStatus('law', 'Researching...', 'active');
  workerPromises.push(sleep(2000).then(() => {
    setAgentStatus('law', 'Complete', 'done');
    return "Phân tích pháp lý hoàn tất.";
  }));
  
  // Tax Worker
  if (needsTax) {
    setAgentStatus('tax', 'Calculating...', 'active');
    workerPromises.push(sleep(2500).then(() => {
      setAgentStatus('tax', 'Complete', 'done');
      return "Phân tích vi phạm thuế hoàn tất.";
    }));
  }
  
  // Privacy Worker
  if (needsPrivacy) {
    setAgentStatus('privacy', 'Checking GDPR...', 'active');
    workerPromises.push(sleep(1800).then(() => {
      setAgentStatus('privacy', 'Complete', 'done');
      return "Phân tích vi phạm dữ liệu cá nhân hoàn tất.";
    }));
  }
  
  await Promise.all(workerPromises);
  
  // 3. Synthesizer Phase
  setAgentStatus('synthesizer', 'Generating Report...', 'active');
  await sleep(1500);
  setAgentStatus('synthesizer', 'Done', 'done');
  
  // Create final report
  let report = "<h3>📊 Báo Cáo Tư Vấn Pháp Lý</h3><br/>";
  report += "<strong>1. Đánh giá sơ bộ:</strong><br/>";
  report += "Dựa trên yêu cầu của bạn, chúng tôi đã tiến hành đánh giá đa khía cạnh.<br/><br/>";
  
  report += "<strong>2. Khía cạnh Dân sự & Thương mại (Law Worker):</strong><br/>";
  report += "Theo Luật Dân sự, hành vi vi phạm hợp đồng có thể chịu phạt vi phạm và bồi thường thiệt hại thực tế.<br/><br/>";
  
  if (needsTax) {
    report += "<strong>3. Khía cạnh Thuế (Tax Worker):</strong><br/>";
    report += "Hành vi trốn thuế có thể bị phạt hành chính từ 1-3 lần số thuế trốn, hoặc truy cứu trách nhiệm hình sự nếu số tiền từ 100 triệu VNĐ.<br/><br/>";
  }
  
  if (needsPrivacy) {
    report += "<strong>4. Khía cạnh Dữ liệu (Privacy Worker):</strong><br/>";
    report += "Việc rò rỉ dữ liệu cá nhân vi phạm Nghị định 13/2023/NĐ-CP, mức phạt có thể lên tới 50-100 triệu VNĐ. Yêu cầu thông báo ngay cho cơ quan chức năng.<br/><br/>";
  }
  
  report += "<em>Khuyến nghị: Công ty cần tiến hành rà soát nội bộ và chuẩn bị hồ sơ giải trình.</em>";
  
  return report;
}

// Handle Form Submit
chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = userInput.value.trim();
  if (!text) return;
  
  // Disable input
  userInput.value = '';
  userInput.disabled = true;
  sendBtn.disabled = true;
  resetAgents();
  
  // Show user message
  appendMessage('user', text);
  appendLoading();
  
  // Run simulation
  const report = await simulateAgentPipeline(text);
  
  // Show result
  removeLoading();
  appendMessage('system', report, true);
  
  // Enable input
  userInput.disabled = false;
  sendBtn.disabled = false;
  userInput.focus();
  
  // Reset agents after a delay
  setTimeout(resetAgents, 3000);
});
