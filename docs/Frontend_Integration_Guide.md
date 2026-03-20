# ByteWallet AI: Frontend & Supabase Integration Guide

**Prepared for: Frontend & Backend Engineering Team**
**Objective:** Seamless integration of the ByteWallet AI Service into the existing Supabase infrastructure and React Native / Mobile Web frontend.

---

## 1. Architecture Overview

The ByteWallet AI system is designed to act as an independent Microservice. It should not directly access the Supabase PostgreSQL database. Instead, your existing Supabase Edge Functions act as the orchestration layer:

1.  **Trigger:** A cron job or user action triggers a Supabase Edge Function.
2.  **Fetch:** The Edge Function queries Supabase (PostgreSQL) to assemble the user's financial snapshot.
3.  **Analyze:** The Edge Function sends an HTTP POST request containing the snapshot to the ByteWallet AI Service (`/v1/predict-burn-rate`).
4.  **Action (The Hybrid Engine):**
    -   **Math First:** The ByteWallet custom ML model instantly calculates the shortfall probability and risk level.
    -   **Safe Route:** If the user is "Within Safety" (Low/Medium Risk), the API skips LLM processing entirely and instantly returns a local, rule-based success message (saving latency and API costs).
    -   **Ollama Route:** If the user is "Above Budget" (High Risk), the API passes the findings to the local **Ollama LLM** (using `qwen2.5` with a 10s fast-fallback). If Ollama is unavailable, the **Adaptive Regex Engine** takes over, identifying specific patterns (e.g., Cafes, Rideshares, Shopping) to generate a hyper-personalized, 2-sentence actionable warning instantly.
5.  **Persist:** The Edge Function saves these results into the Supabase `notifications` and `users` tables.
6.  **Display:** The React Native frontend listens to Supabase Realtime to display Toasts, Badges, and Insights.

---

## 2. Supabase Edge Function Implementation

### 2.1 The Prediction Trigger

Create a Supabase Edge Function (e.g., `process-burn-rate`) triggered daily via Supabase pg_cron or whenever the user opens the app.

```typescript
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const AI_SERVICE_URL = Deno.env.get('BYTEWALLET_AI_URL') || 'http://YOUR_EC2_IP:8000';

serve(async (req) => {
  const { user_id } = await req.json()
  const supabase = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)

  // 1. Fetch User Data Snapshot
  const { data: user } = await supabase.from('users').select('*').eq('user_id', user_id).single()
  
  if (user.is_private) {
    return new Response(JSON.stringify({ status: "skipped_private" }), { status: 200 })
  }

  const { data: budgets } = await supabase.from('budgets').select('*').eq('user_id', user_id)
  const { data: transactions } = await supabase.from('transactions')
    .select('*')
    .eq('user_id', user_id)
    .gt('timestamp', new Date(new Date().setDate(1)).toISOString()) // Current month

  // 2. Map Supabase Schema to AI Schema
  const aiPayload = {
    user_id: user.user_id,
    nickname: user.full_name || user.username,
    currency: user.currency || "VND",
    current_date: new Date().toISOString().split('T')[0],
    balances: {
      banking: user.balance_banking || 0,
      cash: user.balance_cash || 0
    },
    monthly_budget: {
      total: budgets.reduce((acc, b) => acc + Number(b.amount), 0)
    },
    transactions: transactions.map(t => ({
      timestamp: t.timestamp,
      amount: Number(t.amount),
      category: t.category,
      type: t.type,
      note: t.note,
      payment_method: t.payment_method
    }))
  }

  // 3. Call ByteWallet AI Service
  const aiResponse = await fetch(`${AI_SERVICE_URL}/v1/predict-burn-rate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(aiPayload)
  })

  if (!aiResponse.ok) throw new Error("AI Service Error")
  const result = await aiResponse.json()

  // 4. Save Core AI Message to Notifications Table
  if (result.ai_message) {
    await supabase.from('notifications').insert({
      user_id: user_id,
      type: 'ai_insight',
      message: result.ai_message,
      data: { risk_level: result.risk_level, shortfall_prob: result.shortfall_prob }
    })
  }

  // 5. Save Proactive Alerts (Phase 4 Agents)
  if (result.proactive_alerts && result.proactive_alerts.length > 0) {
    const alertsToInsert = result.proactive_alerts.map((alert: any) => ({
      user_id: user_id,
      type: alert.type, // 'anomaly', 'savings', 'subscription'
      message: alert.message,
      data: { title: alert.title, action: alert.suggested_action, ...alert.metadata }
    }))
    await supabase.from('notifications').insert(alertsToInsert)
  }

  return new Response(JSON.stringify({ success: true }), { headers: { 'Content-Type': 'application/json' } })
})
```

---

## 3. React Native Frontend Integration

### 3.1 Real-time Push Notifications (Toasts)

Instead of constantly polling the AI server, the frontend should listen to the `notifications` table using Supabase Realtime. When the Edge Function inserts an `ai_insight` or proactive alert, the app instantly displays a custom Toast.

```javascript
import { useEffect } from 'react';
import { supabase } from '../lib/supabase';
import Toast from 'react-native-toast-message'; // or your preferred toast library

export function useAINotifications(userId) {
  useEffect(() => {
    if (!userId) return;

    const channel = supabase
      .channel('public:notifications')
      .on('postgres_changes', { 
        event: 'INSERT', 
        schema: 'public', 
        table: 'notifications',
        filter: `user_id=eq.${userId}` 
      }, (payload) => {
        const { type, message, data } = payload.new;
        
        let toastType = 'info';
        if (data?.risk_level === 'high' || data?.severity === 'warning') toastType = 'error';

        Toast.show({
          type: toastType,
          text1: data?.title || 'ByteWallet AI Insight',
          text2: message,
          onPress: () => {
             // Navigate to Financial Analysis Screen
          }
        });
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [userId]);
}
```

### 3.2 Dynamic Risk Badge implementation

The AI prediction returns a `risk_level` (low, medium, high). You can fetch the latest notification data or calculate an aggregate state to display a traffic light indicator on the Home Screen next to the Total Balance.

```jsx
// Example Component
const RiskBadge = ({ riskLevel }) => {
  const getRiskColor = () => {
    switch(riskLevel) {
      case 'high': return '#EF4444'; // Red
      case 'medium': return '#F59E0B'; // Yellow
      case 'low': return '#10B981'; // Green
      default: return '#D1D5DB'; // Gray
    }
  };

  return (
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: getRiskColor() }} />
      <Text style={{ marginLeft: 6, color: getRiskColor() }}>
        {riskLevel.toUpperCase()} RISK
      </Text>
    </View>
  );
}
```

#---

## 4. Key Considerations for the Frontend Developer

1. **Security:** Do not expose the ByteWallet AI Server endpoint directly to the mobile app. All traffic must route through the authenticated Supabase Edge Function to prevent payload spoofing.
2. **Speed:** The `/v1/predict-burn-rate` endpoint takes approximately 0.2 to 0.5 seconds to compute locally. It is safe to call during the application startup splash screen.
3. **Graceful Fallbacks:** If the AI service is unreachable, ensure the frontend gracefully degrades to standard, non-predictive balance views.
4. **Data Minimization:** The `Transaction` schema accepts optional fields like `merchant_name`, `latitude`, and `longitude`. If location services are denied on the mobile app, omit them entirely; the AI will gracefully fallback to basic math without throwing validation errors.
