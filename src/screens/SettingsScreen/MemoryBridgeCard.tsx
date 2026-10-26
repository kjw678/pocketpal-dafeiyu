import React, {useEffect, useState} from 'react';
import {View} from 'react-native';
import {Button, Card, Switch, Text, TextInput} from 'react-native-paper';
import {
  clearBridge,
  configureBridge,
  getBridgeAudit,
  getBridgePreferences,
} from '../../services/memory/bridgeHost';

export function MemoryBridgeCard() {
  const [baseUrl, setBaseUrl] = useState('');
  const [token, setToken] = useState('');
  const [allowRecall, setRecall] = useState(false);
  const [allowWrite, setWrite] = useState(false);
  const [status, setStatus] = useState('未配置；不会联网。');
  const [busy, setBusy] = useState(false);
  const [audit, setAudit] = useState('');
  async function refreshAudit() {
    try {
      setAudit(
        (await getBridgeAudit())
          .slice(-6)
          .map(
            e =>
              `${e.at} ${e.operation} ${e.state} ${e.code ?? ''} ${e.request_id ?? ''}`,
          )
          .join('\n'),
      );
    } catch {
      setStatus('本机执行记录暂不可读取。');
    }
  }
  useEffect(() => {
    getBridgePreferences()
      .then(value => {
        setBaseUrl(value.baseUrl);
        setRecall(value.allowRecall);
        setWrite(value.allowWrite);
        setStatus(
          value.configured
            ? '凭据已保存在系统 Keychain；尚未验证服务器。'
            : '未配置；不会联网。',
        );
      })
      .catch(() => setStatus('安全配置读取失败。'));
    refreshAudit();
  }, []);
  async function save() {
    setBusy(true);
    try {
      await configureBridge({baseUrl, token, allowRecall, allowWrite});
      setToken('');
      setStatus('已保存配置；尚未验证服务器。请在 Pal 中启用所需记忆 Talent。');
    } catch {
      setStatus(
        '保存失败：请检查 HTTPS 地址、新目标的独立令牌及 Keychain 可用性。',
      );
    } finally {
      setBusy(false);
    }
  }
  async function clear() {
    setBusy(true);
    try {
      await clearBridge();
      setToken('');
      setRecall(false);
      setWrite(false);
      setStatus('设备凭据已删除；服务端令牌需另行撤销。');
    } catch {
      setStatus('凭据删除失败。');
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card testID="dfy-memory-settings">
      <Card.Title title="大肥鱼 · 私有记忆桥接" />
      <Card.Content>
        <Text>
          默认关闭。仅本地聊天可用。写入每次确认；当前没有随 App
          部署的正式接口。网页读取仍可能经过第三方，私人记忆使用独立通道。
        </Text>
        <TextInput
          label="HTTPS 服务根地址（无查询参数）"
          value={baseUrl}
          onChangeText={setBaseUrl}
          autoCapitalize="none"
          autoCorrect={false}
          maxLength={256}
        />
        <TextInput
          label="独立设备令牌（留空保留同一目标的旧令牌）"
          value={token}
          onChangeText={setToken}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
          maxLength={512}
        />
        <View>
          <Text>允许认证检索</Text>
          <Switch value={allowRecall} onValueChange={setRecall} />
        </View>
        <View>
          <Text>允许提出写入（仍需逐次确认）</Text>
          <Switch value={allowWrite} onValueChange={setWrite} />
        </View>
        <Text>{status}</Text>
        <Button onPress={save} disabled={busy}>
          保存安全配置
        </Button>
        <Button onPress={clear} disabled={busy}>
          删除设备凭据
        </Button>
        <Button onPress={refreshAudit}>刷新本机执行记录</Button>
        <Text selectable>
          {audit || '暂无本机执行记录。工具结果同时保存在聊天回执中。'}
        </Text>
      </Card.Content>
    </Card>
  );
}
