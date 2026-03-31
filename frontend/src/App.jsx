import { useState, useRef, useEffect, useCallback } from 'react';
import { Terminal, Send, Play, TestTube, CheckCircle, ShieldAlert, MonitorUp, HardDrive, FileUp, X, ImagePlus, Check, ExternalLink, Download, Bot, Sparkles, AlertCircle, FileText, ClipboardList, Loader2, Square } from 'lucide-react';
import axios from 'axios';

// The Backend API Endpoint
const API_BASE = "http://localhost:8000/api";

function App() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: '小泽测试助手已就绪。您可以输入指令，或者在左侧配置测试参数后直接执行流水线。' }
  ]);
  const [inputVal, setInputVal] = useState('');
  
  // Sidebar config state
  const [testType, setTestType] = useState('接口/单元测试 (Unit)');
  const [targetURL, setTargetURL] = useState('');
  const [targetFile, setTargetFile] = useState('');
  
  // File Context
  const [contextFile, setContextFile] = useState(null);
  const fileInputRef = useRef(null);

  // Chat Image Context
  const [chatImageFile, setChatImageFile] = useState(null);
  const chatImageInputRef = useRef(null);

  // Visual Regression Modal State
  const [visualData, setVisualData] = useState({ show: false, loading: false, status: '', msg: '', report: '', baseline: null, current: null, diff: null });

  // Execution Output Stream state
  const [logs, setLogs] = useState([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const logsEndRef = useRef(null);
  const chatEndRef = useRef(null);

  // Report state
  const [canExportReport, setCanExportReport] = useState(false);
  const [reportData, setReportData] = useState({ show: false, loading: false, content: '' });
  const [isExporting, setIsExporting] = useState(false);

  // Toast notification system
  const [toasts, setToasts] = useState([]);
  const showToast = useCallback((message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);
  
  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSendMessage = async (e) => {
    e?.preventDefault();
    if (!inputVal.trim() && !chatImageFile) return;
    
    const userMsg = inputVal;

    // --- 【紧急修复】: 参数即时同步 ---
    // 如果用户在聊天里发了 URL，立刻同步到侧边栏，防止测试跑偏
    const qUrlMatch = userMsg.match(/(https?:\/\/[^\s)\]]+)/);
    if (qUrlMatch) {
       const discovered = qUrlMatch[1];
       if (discovered !== targetURL) {
           setTargetURL(discovered);
           if (testType !== 'UI 自动化测试 (Playwright)') {
               setTestType('UI 自动化测试 (Playwright)');
           }
       }
    }
    // ---------------------------------

    setInputVal('');
    const newMessages = [...messages, { role: 'user', content: userMsg || '📷 [已附传图片]' }];
    setMessages(newMessages);
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('prompt', userMsg);
      formData.append('history_json', JSON.stringify(messages));
      formData.append('test_type', testType);
      formData.append('target_url', targetURL);
      formData.append('target_file', targetFile);
      if (contextFile) {
        formData.append('context_file', contextFile);
      }
      if (chatImageFile) {
        formData.append('image_file', chatImageFile);
      }

      const res = await axios.post(`${API_BASE}/chat`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      let reply = res.data.reply || "";
      const shouldRun = res.data.should_run_tests;
      
      // 智能模式检测逻辑：从 AI 回复中提取意图模式
      // 使用本地变量 resolvedMode 来追踪实际生效的模式（避免 React setState 异步陷阱）
      let resolvedMode = testType;  // 默认使用当前状态
      let resolvedURL = targetURL;
      let resolvedFile = targetFile;

      const modeMatch = reply.match(/\[SET_MODE:(UI|UNIT|NORMAL)\]/);
      if (modeMatch) {
          const mode = modeMatch[1];
          const modeMap = {
              'UI': 'UI 自动化测试 (Playwright)',
              'UNIT': '接口/单元测试 (Unit)',
              'NORMAL': '常规模式 (生成文档/用例)'
          };
          const targetMode = modeMap[mode];
          
          if (targetMode) {
              resolvedMode = targetMode;  // 立即更新本地追踪变量
              if (targetMode !== testType) {
                  setTestType(targetMode);
                  showToast(`🔍 小泽识别到新场景，已自动切至 ${mode}`, 'info');
              }
          }
      }

      // 智能 URL 联动逻辑
      const urlMatch = reply.match(/\[SET_URL:(.*?)\]/);
      if (urlMatch) {
          const url = urlMatch[1].trim();
          if (url) {
              resolvedURL = url;
              if (url !== targetURL) {
                  setTargetURL(url);
                  showToast(`🌐 目标 URL 已自动同步：${url}`, 'info');
              }
          }
      }

      // 智能文件路径联动逻辑
      const fileMatch = reply.match(/\[SET_FILE:(.*?)\]/);
      if (fileMatch) {
          const file = fileMatch[1].trim();
          if (file) {
              resolvedFile = file;
              if (file !== targetFile) {
                  setTargetFile(file);
                  showToast(`📁 目标文件已自动同步：${file}`, 'info');
              }
          }
      }

      // 在显示前清洗所有 Token
      reply = reply.replace(/\[SET_MODE:(UI|UNIT|NORMAL)\]/g, "")
                   .replace(/\[SET_URL:.*?\]/g, "")
                   .replace(/\[SET_FILE:.*?\]/g, "")
                   .replace(/\[RUN_TESTS\]/g, "")
                   .trim();

      setMessages(prev => [...prev, { role: 'assistant', content: reply }]);
      setChatImageFile(null);
      
      // 使用 resolvedMode（本地变量）而非 testType（异步状态）来判断是否触发流水线
      if (shouldRun && resolvedMode !== '常规模式 (生成文档/用例)') {
        showToast('🚀 AI 已触发测试流水线执行！', 'success');
        triggerPipeline(userMsg, { url: resolvedURL, file: resolvedFile, mode: resolvedMode });
      } else if (shouldRun && resolvedMode === '常规模式 (生成文档/用例)') {
          showToast('📝 常规模式：已为你生成对应文档/用例，无需自动运行', 'info');
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: `❌ 与服务器通信失败: ${err.message}` }]);
      showToast('与后端服务通信失败', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const triggerPipeline = async (chatPrompt = "", overrides = {}) => {
    // 使用 AI 实时解析的值（overrides），而非可能滞后的 React 状态
    const effectiveURL = overrides.url || targetURL;
    const effectiveFile = overrides.file || targetFile;
    const effectiveMode = overrides.mode || testType;

    // 基础校验
    if (!effectiveFile && !effectiveURL && !contextFile && !chatPrompt) {
        showToast('请先提供测试目标（文件、URL 或 需求说明）', 'error');
        setLogs(prev => [...prev, "❌ 错误：未提供任何测试指标，无法启动流水线。"]);
        return;
    }

    setLogs(["⚡ INITIATING EXECUTION PROTOCOL", "==============================="]);
    setIsExecuting(true);
    showToast('流水线已启动，实时日志已激活', 'info');
    
    try {
      const formData = new FormData();
      formData.append('target_file', effectiveFile);
      formData.append('test_file_out', "test_generated.py");
      formData.append('desc', chatPrompt);
      formData.append('target_url', effectiveURL);
      formData.append('test_type', effectiveMode);
      if (contextFile) {
        formData.append('context_file', contextFile);
      }
      if (chatImageFile) {
        formData.append('image_file', chatImageFile);
      }

      const response = await fetch(`${API_BASE}/test/run`, {
        method: 'POST',
        body: formData
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        // split by new lines and filter empty, then push to logs
        const lines = text.split('\\n').filter(l => l.trim() !== '');
        
        // Use functional state update with batching
        setLogs(prev => {
           return [...prev, ...lines];
        });
      }
    } catch (err) {
       setLogs(prev => [...prev, `[ERROR] Streaming failed: ${err.message}`]);
    } finally {
       setIsExecuting(false);
       setCanExportReport(true);
    }
  };

  const handleStopPipeline = async () => {
    if (!isExecuting) return;
    
    // 立即响应：先重置前端状态，给用户“点击即停止”的流畅感
    setIsExecuting(false);
    setCanExportReport(true);
    
    try {
      setLogs(prev => [...prev, "🛑 手动中断请求已发送..."]);
      const res = await axios.post(`${API_BASE}/test/stop`);
      if (res.data.status === 'success') {
         setLogs(prev => [...prev, `[SYSTEM] 🛑 任务已成功终止。原因: 用户手动熔断。`]);
         showToast('流水线已手动中断', 'warning');
      } else {
         showToast(res.data.message || '终止失败', 'error');
         setLogs(prev => [...prev, `⚠️ 终止失败: ${res.data.message}`]);
      }
    } catch (err) {
      showToast('无法连接后端服务以执行停止操作', 'error');
    }
  };

  const handleMutationTest = async () => {
    setLogs(["☢️ MUTATION ENGINE ACTIVE", "Targeting: " + targetFile, "==============================="]);
    setIsExecuting(true);
    
    try {
      const response = await fetch(`${API_BASE}/test/mutation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_file: targetFile,
          test_file_out: "test_generated.py"
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        setLogs(prev => [...prev, ...decoder.decode(value).split('\\n').filter(l => l)]);
      }
    } catch (err) {
       setLogs(prev => [...prev, `[ERROR] Mutation failed: ${err.message}`]);
    } finally {
       setIsExecuting(false);
    }
  };

  const handleVisualTest = async () => {
    if (!targetURL) {
      alert("请先填写目标 URL");
      return;
    }
    setVisualData(prev => ({ ...prev, show: true, loading: true }));
    try {
      const res = await axios.get(`${API_BASE}/test/visual?target_url=${encodeURIComponent(targetURL)}`);
      if (res.data.status !== "ERROR") {
        setVisualData({
          show: true,
          loading: false,
          status: res.data.status,
          msg: res.data.msg,
          report: res.data.report,
          baseline: res.data.baseline_b64,
          current: res.data.current_b64,
          diff: res.data.diff_b64
        });
      } else {
        setVisualData(prev => ({ ...prev, loading: false, msg: `❌ ${res.data.msg}` }));
      }
    } catch (err) {
      setVisualData(prev => ({ ...prev, loading: false, msg: `❌ ${err.message}` }));
    }
  };

  // 测试报告生成
  const handleGenerateReport = async () => {
    setReportData({ show: true, loading: true, content: '' });
    showToast('🧠 AI 正在深度复盘测试日志...', 'info');
    try {
      const res = await axios.post(`${API_BASE}/report/generate`);
      if (res.data.success) {
        setReportData({ show: true, loading: false, content: res.data.report });
        showToast('✅ 测试报告生成成功！', 'success');
      } else {
        setReportData({ show: false, loading: false, content: '' });
        showToast(res.data.msg || '报告生成失败', 'error');
      }
    } catch (err) {
      setReportData({ show: false, loading: false, content: '' });
      showToast(`报告生成失败: ${err.message}`, 'error');
    }
  };

  // 测试报告导出下载
  const handleExportReport = async () => {
    setIsExporting(true);
    showToast('📦 正在生成并打包报告文件...', 'info');
    try {
      const response = await fetch(`${API_BASE}/report/export`, { method: 'POST' });
      if (!response.ok) throw new Error('Export failed');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `测试报告_${new Date().toISOString().replace(/[:.]/g, '-')}.md`;
      document.body.appendChild(a);
      a.click();
      
      // 延迟释放，防止浏览器下载管理器获取不到文件名
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 1000);
      
      showToast('✅ 报告已成功导出！', 'success');
    } catch (err) {
      showToast(`导出失败: ${err.message}`, 'error');
    } finally {
      setIsExporting(false);
    }
  };

  const handleCIExport = async (platform) => {
    try {
      const res = await axios.post(`${API_BASE}/ci/export`, {
        platform: platform,
        target_file: targetFile || "All Files"
      });
      if (res.data.success) {
        setLogs(prev => [...prev, `[✅ CI/CD] 成功生成并写入 ${platform} 配置文件 -> ${res.data.path}`]);
        showToast(`${platform} 配置已成功生成！`, 'success');
      } else {
        setLogs(prev => [...prev, `[❌ CI/CD] ${res.data.msg}`]);
        showToast('CI/CD 导出失败', 'error');
      }
    } catch (err) {
      setLogs(prev => [...prev, `[❌ CI/CD] 导出失败: ${err.message}`]);
      showToast('CI/CD 导出失败', 'error');
    }
  };

  return (
    <div className="flex h-screen w-full relative">
      {/* Dynamic Gradient Top Border */}
      <div className="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-neon-blue via-neon-purple to-neon-blue z-50"></div>
      
      {/* ===== Left Sidebar: CONFIGURATION ===== */}
      <aside className="w-[320px] bg-obsidian-light/80 backdrop-blur border-r border-white/5 flex flex-col pt-6 pb-4 px-6 relative z-10 shrink-0 shadow-2xl overflow-y-auto">
        <div className="flex items-center gap-3 mb-10 mt-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-blue to-neon-purple shadow-[0_0_12px_rgba(59,130,246,0.5)] flex items-center justify-center">
            <Terminal size={18} className="text-white" />
          </div>
          <h1 className="text-xl font-display font-bold text-white tracking-wide">小泽<span className="text-gray-400 font-normal">测试助手</span></h1>
        </div>

        <div className="space-y-6 flex-1">
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-widest text-[#85ADFF] font-semibold flex flex-row items-center gap-2">
               <TestTube size={14} /> 测试场景
            </label>
            <select 
              className="input-field" 
              value={testType} 
              onChange={e => setTestType(e.target.value)}
            >
              <option>常规模式 (生成文档/用例)</option>
              <option>接口/单元测试 (Unit)</option>
              <option>UI 自动化测试 (Playwright)</option>
              <option>视觉回归测试 (Visual)</option>
            </select>
          </div>

          {/* 目标文件 - 仅 Unit/API 模式显示 */}
          {(testType === '接口/单元测试 (Unit)' || testType === 'API 接口测试 (Swagger)') && (
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-widest text-[#85ADFF] font-semibold flex flex-row items-center gap-2">
               <HardDrive size={14}/> 目标文件
            </label>
            <input 
              type="text" 
              className="input-field" 
              placeholder="例如 src/math_utils.py" 
              value={targetFile}
              onChange={e => setTargetFile(e.target.value)}
            />
          </div>
          )}

          {/* 目标 URL - UI 测试和视觉回归模式显示 */}
          {(testType === 'UI 自动化测试 (Playwright)' || testType === '视觉回归测试 (Visual)') && (
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-widest text-[#85ADFF] font-semibold flex flex-row items-center gap-2">
               <MonitorUp size={14}/> 目标 URL
            </label>
            <input 
              type="text" 
              className="input-field" 
              placeholder="https://example.com" 
              value={targetURL}
              onChange={e => setTargetURL(e.target.value)}
            />
          </div>
          )}

          {/* 常规模式 - 显示两个字段 */}
          {testType === '常规模式 (生成文档/用例)' && (
          <>
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-widest text-[#85ADFF] font-semibold flex flex-row items-center gap-2">
               <HardDrive size={14}/> 目标文件
            </label>
            <input 
              type="text" 
              className="input-field" 
              placeholder="例如 src/math_utils.py" 
              value={targetFile}
              onChange={e => setTargetFile(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-widest text-[#85ADFF] font-semibold flex flex-row items-center gap-2">
               <MonitorUp size={14}/> 目标 URL (可选)
            </label>
            <input 
              type="text" 
              className="input-field" 
              placeholder="https://example.com" 
              value={targetURL}
              onChange={e => setTargetURL(e.target.value)}
            />
          </div>
          </>
          )}

          {/* Context File Upload Section */}
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-widest text-[#85ADFF] font-semibold flex flex-row items-center gap-2">
               <FileUp size={14}/> 附加需求文档 (PRD/接口)
            </label>
            <div 
               onClick={() => fileInputRef.current?.click()}
               className="w-full h-24 border-2 border-dashed border-white/10 rounded-lg flex flex-col items-center justify-center text-gray-500 hover:border-neon-blue/50 hover:bg-neon-blue/5 cursor-pointer transition-all"
            >
               {contextFile ? (
                 <div className="flex flex-col items-center gap-1">
                   <span className="text-xs text-neon-green font-medium truncate max-w-[200px]">{contextFile.name}</span>
                   <button 
                     onClick={(e) => { e.stopPropagation(); setContextFile(null); }}
                     className="text-xs text-gray-400 hover:text-neon-red flex items-center gap-1"
                   >
                     <X size={12}/> 删除文件
                   </button>
                 </div>
               ) : (
                 <>
                   <FileUp size={20} className="mb-2 opacity-50"/>
                   <span className="text-xs">点击上传 .txt / .pdf / .docx</span>
                 </>
               )}
            </div>
            <input 
               type="file" 
               className="hidden" 
               ref={fileInputRef}
               onChange={(e) => {
                 if (e.target.files && e.target.files[0]) {
                   setContextFile(e.target.files[0]);
                 }
               }}
            />
          </div>
        </div>

        <div className="space-y-4 pt-6 border-t border-white/5">
           <button 
             onClick={() => triggerPipeline()}
             disabled={isExecuting}
             className={`flex items-center justify-center gap-2 w-full py-3.5 btn-primary ${isExecuting ? 'opacity-50 cursor-not-allowed' : ''}`}
           >
             <Play size={18} fill="currentColor" />
             {isExecuting ? 'PIPELINE ACTIVE...' : 'EXECUTE PIPELINE'}
           </button>
           
           <button 
              onClick={handleMutationTest}
              disabled={isExecuting}
              className="flex items-center justify-center gap-2 w-full py-3 bg-[#1C2028] text-[#85ADFF] border border-[#85ADFF]/20 rounded-xl hover:bg-neon-blue/10 hover:border-neon-blue transition-all uppercase text-sm font-bold tracking-wide"
           >
             <ShieldAlert size={16} />
             Mutation Engine
           </button>
           
           <div className="flex gap-2 w-full pt-2">
             <button 
               onClick={() => handleCIExport("GitHub Actions")}
               className="flex-1 flex items-center justify-center gap-1 py-2 bg-white/5 border border-white/10 hover:border-gray-400 hover:bg-white/10 rounded-lg text-xs font-bold text-gray-300 transition-all uppercase"
             >
               <Download size={14} /> Github
             </button>
             <button 
               onClick={() => handleCIExport("GitLab CI")}
               className="flex-1 flex items-center justify-center gap-1 py-2 bg-white/5 border border-white/10 hover:border-gray-400 hover:bg-white/10 rounded-lg text-xs font-bold text-gray-300 transition-all uppercase"
             >
               <Download size={14} /> GitLab
             </button>
           </div>
        </div>
      </aside>

      {/* ===== Middle: MAIN CHAT INTERFACE ===== */}
      <main className="flex-1 flex flex-col relative min-w-[500px] z-0">
        <div className="h-16 border-b border-white/5 flex items-center px-8 shrink-0 bg-transparent">
          <h2 className="font-display font-medium text-gray-300">小泽测试助手 - 核心控制台</h2>
          {isExecuting && (
            <div className="ml-auto flex items-center gap-2 text-neon-green text-sm font-mono animate-pulse">
               <span className="w-2 h-2 rounded-full bg-neon-green shadow-[0_0_8px_#10B981]"></span>
               PROCESSING
            </div>
          )}
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-8 space-y-6 scroll-smooth">
          {messages.map((msg, i) => (
             <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-[fadeSlideIn_0.3s_ease-out]`}>
               {msg.role === 'assistant' && (
                 <div className="w-8 h-8 rounded-full bg-gradient-to-br from-neon-purple to-neon-blue flex items-center justify-center mr-3 mt-1 shrink-0 shadow-[0_0_10px_rgba(139,92,246,0.4)]">
                    <Bot size={16} className="text-white" />
                 </div>
               )}
               <div className={`max-w-[70%] text-sm leading-relaxed p-4 rounded-2xl ${
                 msg.role === 'user' 
                 ? 'bg-neon-blue/10 border border-neon-blue/20 text-[#ECEDF6]' 
                 : 'glass-panel text-gray-300'
               }`}>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
               </div>
             </div>
          ))}

          {/* Loading Robot Animation */}
          {isLoading && (
             <div className="flex justify-start animate-[fadeSlideIn_0.3s_ease-out]">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-neon-purple to-neon-blue flex items-center justify-center mr-3 mt-1 shrink-0 shadow-[0_0_10px_rgba(139,92,246,0.4)]">
                   <Bot size={16} className="text-white animate-spin" style={{ animationDuration: '2s' }} />
                </div>
                <div className="glass-panel text-gray-400 px-5 py-4 rounded-2xl flex items-center gap-3">
                   <div className="flex gap-1">
                      <span className="w-2 h-2 rounded-full bg-neon-blue animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="w-2 h-2 rounded-full bg-neon-purple animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="w-2 h-2 rounded-full bg-neon-blue animate-bounce" style={{ animationDelay: '300ms' }}></span>
                   </div>
                   <span className="text-sm font-mono tracking-wide">AI 正在深度思考中...</span>
                   <Sparkles size={14} className="text-neon-purple animate-pulse" />
                </div>
             </div>
          )}
          <div ref={chatEndRef}></div>
        </div>

         {/* Chat Input */}
        <div className="p-6 pt-0 bg-gradient-to-t from-obsidian to-transparent">
           {chatImageFile && (
             <div className="mb-3 flex items-center gap-2 bg-neon-blue/10 border border-neon-blue/20 px-4 py-2 rounded-lg w-max text-sm text-neon-blue">
                <ImagePlus size={16} />
                <span className="truncate max-w-[200px]">{chatImageFile.name}</span>
                <button onClick={() => setChatImageFile(null)} className="hover:text-neon-red ml-2"><X size={14} /></button>
             </div>
           )}
           <form onSubmit={handleSendMessage} className="relative flex items-center">
             <input type="file" accept="image/*" className="hidden" ref={chatImageInputRef} onChange={(e) => {
                 if (e.target.files && e.target.files[0]) setChatImageFile(e.target.files[0]);
             }} />
             
             <button 
                type="button" 
                onClick={() => chatImageInputRef.current?.click()}
                className="absolute left-3 p-2 text-gray-400 hover:text-neon-blue transition-all z-10"
                title="附传图片用于视觉识别分析"
             >
                <ImagePlus size={20} />
             </button>

             <input 
                type="text" 
                value={inputVal}
                onChange={e => setInputVal(e.target.value)}
                placeholder="发送指令，或上传截图问我..."
                className="w-full bg-[#1C2028] border border-white/10 text-white rounded-xl py-4 pl-12 pr-14 focus:outline-none focus:border-neon-blue focus:ring-1 focus:ring-neon-blue transition-all font-sans"
             />
             <button type="submit" className="absolute right-3 p-2 bg-neon-blue rounded-lg text-white hover:bg-white hover:text-neon-blue transition-all">
               <Send size={18} />
             </button>
           </form>
        </div>
      </main>

      {/* ===== Right Sidebar: TERMINAL & RESULTS ===== */}
      <aside className="w-[450px] bg-[#0E1118] border-l border-white/5 flex flex-col shrink-0">
         <div className="h-16 flex items-center justify-between px-6 border-b border-white/5">
            <h3 className="text-xs uppercase tracking-widest font-bold text-gray-400">Execution Monitor</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={handleGenerateReport}
                disabled={!canExportReport || isExecuting}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold uppercase tracking-wide rounded-lg border transition-all ${
                  canExportReport && !isExecuting
                    ? 'bg-neon-purple/10 text-neon-purple border-neon-purple/30 hover:bg-neon-purple hover:text-white cursor-pointer'
                    : 'bg-white/5 text-gray-600 border-white/10 cursor-not-allowed'
                }`}
                title={canExportReport ? '生成 AI 深度复盘报告' : '请先执行一次测试'}
              >
                <ClipboardList size={13} />
                报告
              </button>
              {/* 清除按钮 - 始终可见 */}
              <button
                onClick={() => { setLogs([]); setCanExportReport(false); }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold uppercase tracking-wide rounded-lg border bg-white/5 text-gray-400 border-white/10 hover:bg-white/10 hover:text-white cursor-pointer transition-all"
                title="清除日志面板"
              >
                <X size={13} />
                清除
              </button>

              {/* 中止按钮 - 始终可见，执行中高亮闪烁 */}
              <button
                onClick={handleStopPipeline}
                disabled={!isExecuting}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold uppercase tracking-wide rounded-lg border transition-all ${
                  isExecuting
                    ? 'bg-neon-red/10 text-neon-red border-neon-red/30 hover:bg-neon-red hover:text-white cursor-pointer animate-pulse'
                    : 'bg-white/5 text-gray-600 border-white/10 cursor-not-allowed'
                }`}
                title={isExecuting ? '强制停止当前流水线' : '当前无任务运行'}
              >
                <Square size={13} fill="currentColor" />
                中止
              </button>

              <button
                onClick={handleExportReport}
                disabled={!canExportReport || isExporting}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold uppercase tracking-wide rounded-lg border transition-all ${
                  canExportReport && !isExporting
                    ? 'bg-neon-green/10 text-neon-green border-neon-green/30 hover:bg-neon-green hover:text-black cursor-pointer'
                    : 'bg-white/5 text-gray-600 border-white/10 cursor-not-allowed'
                }`}
                title={canExportReport ? '导出 Markdown 报告文件' : '请先执行一次测试'}
              >
                {isExporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                导出
              </button>
            </div>
         </div>
         
         {/* Live Logs Terminal */}
         <div className="flex-1 p-5 overflow-y-auto bg-black m-4 rounded-xl border border-white/5 shadow-inner">
            <div className="font-mono text-xs font-medium space-y-2">
               {logs.length === 0 ? (
                  <div className="text-gray-600 italic">Waiting for execution...</div>
               ) : (
                 logs.map((L, i) => {
                    let colorClass = 'text-gray-400';
                    if (L.includes('ERROR') || L.includes('FAILED') || L.includes('❌') || L.includes('💥')) colorClass = 'text-neon-red font-bold';
                    else if (L.includes('PASS') || L.includes('SUCCESS') || L.includes('✅') || L.includes('🏆')) colorClass = 'text-neon-green font-bold';
                    else if (L.includes('[REFLECTION]') || L.includes('🧠') || L.includes('🔧') || L.includes('🚨')) colorClass = 'text-[#FF9F1C] font-bold animate-pulse shadow-sm';
                    else if (L.includes('[AGENT: 👨‍💼')) colorClass = 'text-[#00F0FF] font-bold drop-shadow-[0_0_2px_rgba(0,240,255,0.8)]';
                    else if (L.includes('[AGENT: 🧑‍💻')) colorClass = 'text-[#B026FF] font-bold drop-shadow-[0_0_2px_rgba(176,38,255,0.8)]';
                    else if (L.includes('[AGENT: 🕵️‍♂️')) colorClass = 'text-[#FFF000] font-bold drop-shadow-[0_0_2px_rgba(255,240,0,0.8)]';
                    else if (L.startsWith('==')) colorClass = 'text-neon-blue font-bold';
                    
                    return (
                        <div key={i} className={colorClass}>
                          {L}
                        </div>
                    );
                 })
               )}
               <div ref={logsEndRef}></div>
            </div>
         </div>
         
         {/* Fake UI Report Panel -> Native Visual Testing Trigger */}
         <div className="h-[250px] p-5 border-t border-white/5 bg-[#10131A] flex flex-col items-center justify-center text-center">
            <CheckCircle size={28} className="text-neon-green mb-3 opacity-80" />
            <h4 className="text-sm font-bold text-gray-200 mb-2">Visual Integrity Scanner</h4>
            <p className="text-xs text-gray-500 mb-4 px-4 leading-relaxed">捕捉像素级界面变动，由 GLM-4v 提供大模型审美评估意见。</p>
            <button
               onClick={handleVisualTest}
               className="px-6 py-2 bg-neon-green/10 text-neon-green border border-neon-green/30 hover:bg-neon-green hover:text-black rounded-lg text-sm font-bold tracking-wider transition-all"
            >
               RUN VISUAL SCAN
            </button>
         </div>
      </aside>

      {/* ===== Visual Regression Modal ===== */}
      {visualData.show && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-md">
           <div className="bg-[#10131A] border border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.8)] rounded-2xl w-[90vw] max-w-6xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
              <div className="p-5 border-b border-white/5 flex items-center justify-between bg-obsidian-light/50">
                 <div className="flex items-center gap-3">
                    <MonitorUp size={20} className="text-neon-blue" />
                    <h2 className="text-lg font-bold text-white tracking-wide">视觉回归检测报告 <span className="text-gray-500 font-normal ml-2">{targetURL}</span></h2>
                 </div>
                 <button onClick={() => setVisualData(prev => ({ ...prev, show: false }))} className="text-gray-500 hover:text-white transition-colors bg-white/5 p-1 rounded">
                    <X size={20} />
                 </button>
              </div>

              <div className="p-6 overflow-y-auto flex-1 h-full">
                 {visualData.loading ? (
                    <div className="h-64 flex flex-col items-center justify-center gap-4">
                       <div className="w-10 h-10 border-4 border-neon-blue border-t-transparent rounded-full animate-spin"></div>
                       <p className="text-neon-blue tracking-widest font-mono text-sm uppercase">Capturing Visual Map & Analyzing...</p>
                    </div>
                 ) : (
                    <div className="space-y-8">
                       <div className="bg-[#1C2028] border border-white/5 rounded-xl p-5">
                          <h3 className="text-[#85ADFF] font-bold mb-3 flex items-center gap-2"><TestTube size={16}/> 分析结论: {visualData.status}</h3>
                          <p className="text-sm text-gray-300 leading-relaxed">{visualData.msg}</p>
                          {visualData.report && (
                            <div className="mt-4 p-4 bg-black/30 rounded-lg border border-white/5">
                               <p className="text-sm text-gray-400 whitespace-pre-wrap">{visualData.report}</p>
                            </div>
                          )}
                       </div>

                       <div className="grid grid-cols-3 gap-6">
                            <div className="flex flex-col gap-2">
                               <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">Baseline (基准)</span>
                               <div className="bg-black border border-white/10 rounded-lg p-1 aspect-[4/3] flex items-center justify-center overflow-hidden">
                                  {visualData.baseline ? <img src={visualData.baseline} className="object-contain w-full h-full" alt="baseline" /> : <span className="text-xs text-gray-700">No Image</span>}
                               </div>
                            </div>
                            <div className="flex flex-col gap-2">
                               <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">Current (当前测试)</span>
                               <div className="bg-black border border-white/10 rounded-lg p-1 aspect-[4/3] flex items-center justify-center overflow-hidden">
                                  {visualData.current ? <img src={visualData.current} className="object-contain w-full h-full" alt="current" /> : <span className="text-xs text-gray-700">No Image</span>}
                               </div>
                            </div>
                            <div className="flex flex-col gap-2">
                               <span className="text-xs font-bold text-neon-red uppercase tracking-widest">Diff Map (变动标红)</span>
                               <div className="bg-black border border-white/10 rounded-lg p-1 aspect-[4/3] flex items-center justify-center overflow-hidden relative">
                                  {visualData.diff ? (
                                     <>
                                        <img src={visualData.diff} className="object-contain w-full h-full" alt="diff" />
                                        <div className="absolute top-2 right-2 flex gap-1">
                                          <span className="w-2 h-2 rounded-full bg-neon-red shadow-[0_0_8px_#EF4444] animate-pulse"></span>
                                        </div>
                                     </>
                                  ) : <span className="text-xs text-gray-700">No Target / Identical</span>}
                               </div>
                            </div>
                       </div>
                    </div>
                 )}
              </div>
           </div>
        </div>
      )}

      {/* ===== Report Preview Modal ===== */}
      {reportData.show && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-md">
           <div className="bg-[#10131A] border border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.8)] rounded-2xl w-[90vw] max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
              <div className="p-5 border-b border-white/5 flex items-center justify-between bg-obsidian-light/50">
                 <div className="flex items-center gap-3">
                    <FileText size={20} className="text-neon-purple" />
                    <h2 className="text-lg font-bold text-white tracking-wide">🧪 AI 测试报告</h2>
                 </div>
                 <div className="flex items-center gap-2">
                    <button 
                      onClick={handleExportReport}
                      disabled={isExporting || reportData.loading}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold uppercase tracking-wide rounded-lg border bg-neon-green/10 text-neon-green border-neon-green/30 hover:bg-neon-green hover:text-black transition-all"
                    >
                      {isExporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                      导出 .md
                    </button>
                    <button onClick={() => setReportData(prev => ({ ...prev, show: false }))} className="text-gray-500 hover:text-white transition-colors bg-white/5 p-1 rounded">
                       <X size={20} />
                    </button>
                 </div>
              </div>

              <div className="p-6 overflow-y-auto flex-1">
                 {reportData.loading ? (
                    <div className="h-64 flex flex-col items-center justify-center gap-4">
                       <div className="w-10 h-10 border-4 border-neon-purple border-t-transparent rounded-full animate-spin"></div>
                       <p className="text-neon-purple tracking-widest font-mono text-sm uppercase">AI 正在深度分析测试日志...</p>
                    </div>
                 ) : (
                    <div className="prose prose-invert max-w-none">
                       <pre className="whitespace-pre-wrap text-sm text-gray-300 leading-relaxed font-sans bg-transparent p-0 m-0">{reportData.content}</pre>
                    </div>
                 )}
              </div>
           </div>
        </div>
      )}

      {/* ===== Toast Notification Stack ===== */}
      <div className="fixed top-6 right-6 z-[200] flex flex-col gap-3 pointer-events-none">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-center gap-3 px-5 py-3 rounded-xl shadow-2xl backdrop-blur-md border animate-[slideInRight_0.3s_ease-out] ${
              toast.type === 'success' ? 'bg-neon-green/10 border-neon-green/30 text-neon-green' :
              toast.type === 'error' ? 'bg-neon-red/10 border-neon-red/30 text-neon-red' :
              'bg-neon-blue/10 border-neon-blue/30 text-neon-blue'
            }`}
          >
            {toast.type === 'success' && <CheckCircle size={18} />}
            {toast.type === 'error' && <AlertCircle size={18} />}
            {toast.type === 'info' && <Sparkles size={18} />}
            <span className="text-sm font-medium">{toast.message}</span>
          </div>
        ))}
      </div>

    </div>
  );
}

export default App;
