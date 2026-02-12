with open('src/components/SearchInterface.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 移除高级选项面板，改用从localStorage读取预设
old_state = '''// 搜索参数状态
  const [useRerank, setUseRerank] = useState(true);
  const [useQueryEnhance, setUseQueryEnhance] = useState(false);
  const [recallSize, setRecallSize] = useState(15);'''

new_state = '''// 搜索精度预设（从系统设置读取）
  const [searchConfig, setSearchConfig] = useState({
    useRerank: true,
    useQueryEnhance: false,
    recallSize: 15
  });
  
  // 加载搜索配置
  useEffect(() => {
    const loadConfig = () => {
      const preset = localStorage.getItem('searchPreset') || 'normal';
      const configs: Record<string, any> = {
        fast: { useRerank: false, useQueryEnhance: false, recallSize: 10 },
        normal: { useRerank: true, useQueryEnhance: false, recallSize: 15 },
        precise: { useRerank: true, useQueryEnhance: true, recallSize: 30 }
      };
      setSearchConfig(configs[preset] || configs.normal);
    };
    
    loadConfig();
    
    // 监听storage变化（其他标签页修改设置）
    window.addEventListener('storage', loadConfig);
    return () => window.removeEventListener('storage', loadConfig);
  }, []);'''

content = content.replace(old_state, new_state)

# 修改搜索请求参数
old_search_params = '''params: { 
          q: value, 
          limit: 10,
          use_rerank: useRerank,
          use_query_enhance: useQueryEnhance,
          recall_size: recallSize
        },'''

new_search_params = '''params: { 
          q: value, 
          limit: 10,
          use_rerank: searchConfig.useRerank,
          use_query_enhance: searchConfig.useQueryEnhance,
          recall_size: searchConfig.recallSize
        },'''

content = content.replace(old_search_params, new_search_params)

# 移除高级选项面板
old_advanced = '''        </AutoComplete>
        
        {/* 高级搜索选项 */}
        <Collapse 
          ghost 
          style={{ marginTop: 12 }}
          items={[{
            key: '1',
            label: <span><SettingOutlined /> 高级选项</span>,
            children: (
              <div style={{ padding: '8px 0' }}>
                <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>重排序（提高准确率）</span>
                  <Switch checked={useRerank} onChange={setUseRerank} />
                </div>
                <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>查询增强（提高召回率）</span>
                  <Switch checked={useQueryEnhance} onChange={setUseQueryEnhance} />
                </div>
                <div style={{ marginBottom: 8 }}>
                  <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
                    <span>召回数量</span>
                    <span style={{ color: '#666' }}>{recallSize} 个</span>
                  </div>
                  <Slider 
                    min={5} 
                    max={50} 
                    value={recallSize} 
                    onChange={setRecallSize}
                    marks={{ 5: '5', 15: '15', 30: '30', 50: '50' }}
                  />
                </div>
              </div>
            )
          }]}
        />
      </Card>'''

new_advanced = '''        </AutoComplete>
        <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
          搜索精度可在「系统设置」中调整
        </div>
      </Card>'''

content = content.replace(old_advanced, new_advanced)

# 移除不再需要的import
old_import = "import { Input, Button, List, Card, Tag, AutoComplete, Spin, Progress, Switch, Slider, Collapse } from 'antd';"
new_import = "import { Input, Button, List, Card, Tag, AutoComplete, Spin, Progress } from 'antd';"
content = content.replace(old_import, new_import)

old_icons = "import { SearchOutlined, LoadingOutlined, SettingOutlined } from '@ant-design/icons';"
new_icons = "import { SearchOutlined, LoadingOutlined } from '@ant-design/icons';"
content = content.replace(old_icons, new_icons)

with open('src/components/SearchInterface.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print('SearchInterface更新完成')
