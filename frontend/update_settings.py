with open('src/components/Settings.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 添加搜索精度预设
old_import = "import { Card, Form, Input, Button, Switch, Select, message, Spin } from 'antd';"
new_import = "import { Card, Form, Input, Button, Switch, Select, message, Spin, Radio, Divider } from 'antd';"
content = content.replace(old_import, new_import)

# 添加搜索精度状态和配置定义
old_state = '''const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);'''

new_state = '''const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searchPreset, setSearchPreset] = useState<string>('normal');

  // 搜索精度预设配置
  const SEARCH_PRESETS = {
    fast: { name: '低精度高速度', useRerank: false, useQueryEnhance: false, recallSize: 10 },
    normal: { name: '正常', useRerank: true, useQueryEnhance: false, recallSize: 15 },
    precise: { name: '高精度低速度', useRerank: true, useQueryEnhance: true, recallSize: 30 }
  };'''

content = content.replace(old_state, new_state)

# 修改useEffect加载配置
old_effect = '''// 加载系统配置
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await axios.get(`${API_BASE}/config`);
        form.setFieldsValue({
          embedding_model: response.data.embedding_model || 'BAAI/bge-small-zh-v1.5',
          chunk_size: response.data.chunk_size || 800,
          top_k: response.data.top_k || 10,
          enable_ocr: response.data.enable_ocr ?? true,
        });
      } catch (error) {
        // 使用默认值
        form.setFieldsValue({
          embedding_model: 'BAAI/bge-small-zh-v1.5',
          chunk_size: 800,
          top_k: 10,
          enable_ocr: true,
        });
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
  }, [form]);'''

new_effect = '''// 加载系统配置
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await axios.get(`${API_BASE}/config`);
        form.setFieldsValue({
          embedding_model: response.data.embedding_model || 'BAAI/bge-small-zh-v1.5',
          chunk_size: response.data.chunk_size || 800,
          top_k: response.data.top_k || 10,
          enable_ocr: response.data.enable_ocr ?? true,
        });
      } catch (error) {
        // 使用默认值
        form.setFieldsValue({
          embedding_model: 'BAAI/bge-small-zh-v1.5',
          chunk_size: 800,
          top_k: 10,
          enable_ocr: true,
        });
      }
      
      // 加载搜索精度预设
      const savedPreset = localStorage.getItem('searchPreset') || 'normal';
      setSearchPreset(savedPreset);
      
      setLoading(false);
    };
    fetchConfig();
  }, [form]);

  // 保存搜索精度预设
  const handlePresetChange = (value: string) => {
    setSearchPreset(value);
    localStorage.setItem('searchPreset', value);
    message.success(`已切换为: ${SEARCH_PRESETS[value as keyof typeof SEARCH_PRESETS].name}`);
  };'''

content = content.replace(old_effect, new_effect)

# 在表单中添加搜索精度预设选项
old_form_content = '''<Form.Item
          label="启用OCR"
          name="enable_ocr"
          valuePropName="checked"
          extra="对图片类文档进行文字识别"
        >
          <Switch />
        </Form.Item>

        <Form.Item>'''

new_form_content = '''<Form.Item
          label="启用OCR"
          name="enable_ocr"
          valuePropName="checked"
          extra="对图片类文档进行文字识别"
        >
          <Switch />
        </Form.Item>

        <Divider />

        <Form.Item label="搜索精度预设" extra="调整搜索速度与准确率的平衡">
          <Radio.Group value={searchPreset} onChange={(e) => handlePresetChange(e.target.value)}>
            <Radio.Button value="fast">低精度高速度</Radio.Button>
            <Radio.Button value="normal">正常</Radio.Button>
            <Radio.Button value="precise">高精度低速度</Radio.Button>
          </Radio.Group>
        </Form.Item>
        
        <div style={{ padding: 12, background: '#f5f5f5', borderRadius: 6, marginBottom: 16 }}>
          <div style={{ fontWeight: 500, marginBottom: 8 }}>当前模式: {SEARCH_PRESETS[searchPreset as keyof typeof SEARCH_PRESETS].name}</div>
          <div style={{ fontSize: 13, color: '#666' }}>
            {searchPreset === 'fast' && '关闭重排序，召回10个候选。适合快速浏览，速度最快。'}
            {searchPreset === 'normal' && '开启重排序，召回15个候选。速度与准确率平衡，推荐日常使用。'}
            {searchPreset === 'precise' && '开启重排序和查询增强，召回30个候选。准确率最高，速度较慢。'}
          </div>
        </div>

        <Form.Item>'''

content = content.replace(old_form_content, new_form_content)

with open('src/components/Settings.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print('Settings更新完成')
