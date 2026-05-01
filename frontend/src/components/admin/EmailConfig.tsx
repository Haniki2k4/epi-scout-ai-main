import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Mail, Save, Eye, EyeOff, CheckCircle2, FlaskConical, Send } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface EmailConfigData {
  sender_email: string | null;
  has_api_key: boolean;
  has_inbox_id: boolean;
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const EmailConfig = () => {
  const { toast } = useToast();
  const [config, setConfig] = useState<EmailConfigData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Form state
  const [apiToken, setApiToken] = useState("");
  const [showApiToken, setShowApiToken] = useState(false);
  const [inboxId, setInboxId] = useState("");
  const [senderEmail, setSenderEmail] = useState("");

  useEffect(() => { fetchConfig(); }, []);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/report/email-config", { headers: authHeaders() });
      if (!res.ok) throw new Error("Failed");
      const data: EmailConfigData = await res.json();
      setConfig(data);
      setSenderEmail(data.sender_email || "");
    } catch {
      toast({ title: "Lỗi", description: "Không thể tải cấu hình email", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        sender_email: senderEmail.trim() || null,
        mailtrap_inbox_id: inboxId.trim() || null,
      };

      if (apiToken.trim()) {
        body.mailtrap_api_token = apiToken.trim();
      }

      const res = await fetch("/api/report/email-config", {
        method: "PUT",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) throw new Error("Failed");
      const data: EmailConfigData = await res.json();
      setConfig(data);
      setApiToken(""); // Clear sau khi lưu
      toast({ title: "Đã lưu", description: "Cấu hình email đã được cập nhật" });
    } catch {
      toast({ title: "Lỗi", description: "Không thể lưu cấu hình", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-center text-muted-foreground py-8">Đang tải...</div>;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Mail className="h-5 w-5 text-primary" />
            Cấu hình Gửi Email (Mailtrap)
          </CardTitle>
          <CardDescription>
            Hệ thống hỗ trợ cả chế độ <strong>Email Testing (Sandbox)</strong> để thử nghiệm và <strong>Email Sending</strong> để gửi thật.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          
          <Alert variant="default" className="bg-blue-50 border-blue-200">
            <FlaskConical className="h-4 w-4 text-blue-600" />
            <AlertTitle className="text-blue-800">Hướng dẫn Testing</AlertTitle>
            <AlertDescription className="text-blue-700 text-xs">
              Để dùng <strong>Email Testing (Sandbox)</strong>: Nhập API Token và <strong>Inbox ID</strong>. 
              Mọi email sẽ được chặn lại trong hòm thư ảo của Mailtrap, không gửi đến người dùng thật.
            </AlertDescription>
          </Alert>

          {/* Mailtrap API Token */}
          <div className="space-y-2">
            <Label htmlFor="mt-api-token">Mailtrap API Token</Label>
            <div className="flex gap-2">
              <Input
                id="mt-api-token"
                type={showApiToken ? "text" : "password"}
                placeholder={config?.has_api_key ? "••••••••• (đã cấu hình)" : "Nhập Mailtrap API Token..."}
                value={apiToken}
                onChange={e => setApiToken(e.target.value)}
                className="font-mono text-sm"
              />
              <Button
                variant="outline" size="icon"
                onClick={() => setShowApiToken(!showApiToken)}
                type="button"
              >
                {showApiToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
            {config?.has_api_key && (
              <div className="flex items-center gap-1.5 text-xs text-green-600">
                <CheckCircle2 className="h-3.5 w-3.5" />
                API Token đã được cấu hình.
              </div>
            )}
          </div>

          {/* Mailtrap Inbox ID */}
          <div className="space-y-2">
            <Label htmlFor="mt-inbox-id">Mailtrap Inbox ID (Chỉ dành cho Testing/Sandbox)</Label>
            <Input
              id="mt-inbox-id"
              type="text"
              placeholder={config?.has_inbox_id ? "(đã cấu hình)" : "Ví dụ: 1234567"}
              value={inboxId}
              onChange={e => setInboxId(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Bỏ trống nếu muốn dùng chế độ <strong>Email Sending (Production)</strong> để gửi email thật.
            </p>
          </div>

          {/* Sender email */}
          <div className="space-y-2">
            <Label htmlFor="sender-email">Địa chỉ email gửi (From)</Label>
            <Input
              id="sender-email"
              type="email"
              placeholder="baocao@episcout.ai"
              value={senderEmail}
              onChange={e => setSenderEmail(e.target.value)}
            />
            <p className="text-xs text-muted-foreground italic">
              * Với chế độ Production: Phải là domain đã xác minh. <br/>
              * Với chế độ Sandbox: Có thể nhập bất kỳ email nào để test hiển thị.
            </p>
          </div>

          <div className="pt-2">
            <Button onClick={handleSave} disabled={saving} className="gap-2 w-full sm:w-auto">
              <Save className="h-4 w-4" />
              {saving ? "Đang lưu..." : "Lưu cấu hình"}
            </Button>
          </div>

          <div className="mt-4 p-4 rounded-lg border bg-muted/30">
            <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
              <Send className="h-4 w-4" /> 
              Cách lấy thông tin:
            </h4>
            <ul className="text-xs space-y-1 text-muted-foreground list-disc pl-4">
              <li><strong>API Token:</strong> Mailtrap Dashboard → User Settings → API Tokens</li>
              <li><strong>Inbox ID:</strong> Mailtrap Dashboard → Email Testing → Inboxes → Chọn Inbox của bạn → Xem ID trên URL (ví dụ: inboxes/<b>1234567</b>)</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default EmailConfig;
