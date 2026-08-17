# UniDeer - 2.0

[English](./README.md) | [中文](./README_zh.md) | 日本語 | [Français](./README_fr.md) | [Русский](./README_ru.md)

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

UniDeer（**D**eep **E**xploration and **E**fficient **R**esearch **Flow**）は、**LangGraph** 上に構築されたオープンソースの**スーパーエージェントハーネス**です。**サブエージェント**、**長期メモリ**、**サンドボックス実行**を統合し、複雑なマルチステップタスクを処理します。すべて**拡張可能なスキル**によって支えられています。

UniDeer は、[**DeerFlow**](https://github.com/bytedance/deer-flow)（[**ByteDance**](https://www.bytedance.com/) が作成、v2.0+）の**コミュニティフォーク**であり、独自のエンジニアリング方向性を持つ独立したプロジェクトへと進化しました。ディープリサーチの系譜と元のアーキテクチャの多くを共有していますが、コードベース、ミドルウェアパイプライン、ランタイムの動作は再設計されています。[UniDeer と DeerFlow の違い](#unideer-と-deerflow-の違い)と[謝辞](#謝辞)を参照してください。

> **系譜についての注記：** DeerFlow 2.0 はゼロからの完全な書き直しで、v1 とはコードを共有していません。UniDeer はその 2.0 の基盤の上に構築され、そこから発展を続けています。オリジナルの v1 ディープリサーチフレームワークは、上流の [1.x ブランチ](https://github.com/bytedance/deer-flow/tree/main-1.x) で引き続きメンテナンスされています。

---

## 目次

- [UniDeer を選ぶ理由](#unideer-を選ぶ理由)
  - [「チャットボット＋ツール」の問題](#チャットボットツールの問題)
  - [設計原則](#設計原則)
- [謝辞](#謝辞)
- [UniDeer と DeerFlow の違い](#unideer-と-deerflow-の違い)
- [アーキテクチャ概要](#アーキテクチャ概要)
  - [サービストポロジー](#サービストポロジー)
  - [ハーネスとアプリの依存ファイアウォール](#ハーネスとアプリの依存ファイアウォール)
  - [典型的なリクエストのエンドツーエンド](#典型的なリクエストのエンドツーエンド)
- [コア機能](#コア機能)
  - [スキルとツール](#スキルとツール)
  - [ミドルウェアパイプライン](#ミドルウェアパイプライン)
  - [サブエージェント](#サブエージェント)
  - [サンドボックスとファイルシステム](#サンドボックスとファイルシステム)
  - [コンテキストエンジニアリング](#コンテキストエンジニアリング)
  - [長期メモリ](#長期メモリ)
  - [MCP とモデルファクトリー](#mcp-とモデルファクトリー)
  - [ツールカタログ](#ツールカタログ)
- [ランタイムと信頼性](#ランタイムと信頼性)
  - [実行の所有権、リース、リカバリ](#実行の所有権リースリカバリ)
  - [チェックポインティング](#チェックポインティング)
  - [データベースレベルの並行性インバリアント](#データベースレベルの並行性インバリアント)
- [クイックスタート](#クイックスタート)
  - [前提条件](#前提条件)
  - [設定](#設定)
  - [アプリケーションの起動](#アプリケーションの起動)
  - [起動モード](#起動モード)
- [アドバンスト](#アドバンスト)
  - [サンドボックスプロバイダー](#サンドボックスプロバイダー)
  - [IM チャネル](#im-チャネル)
  - [認可と RBAC](#認可と-rbac)
  - [トレーシングと可観測性](#トレーシングと可観測性)
  - [スケジュールタスク](#スケジュールタスク)
  - [プロビジョナー（Kubernetes）](#プロビジョナーkubernetes)
- [組み込み Python クライアント](#組み込み-python-クライアント)
- [ターミナルワークベンチ（TUI）](#ターミナルワークベンチtui)
- [デプロイ](#デプロイ)
  - [ローカル開発](#ローカル開発)
  - [Docker](#docker)
  - [Kubernetes](#kubernetes)
- [セキュリティ](#セキュリティ)
- [ドキュメント](#ドキュメント)
- [コントリビューション](#コントリビューション)
- [ライセンス](#ライセンス)

---

## UniDeer を選ぶ理由

ほとんどの「AI エージェント」ツールは、検索ツールを付けたチャットインターフェースに過ぎません。UniDeer は**ハーネス**です。確率的な LLM 生成を、決定的でステートマシン管理された実行パイプラインに変える構造化ランタイムです。

1 回のリクエストは次のように流れます：

1. **リードエージェント** — ターンを計画し、委任するかどうかを判断し、最終回答を統合します
2. **ミドルウェアチェーン** — 35 以上の合成可能なインターセプターからなるパイプラインで、各モデル呼び出しとツール実行の前後に、スキル、予算、安全性、ツールポリシーを強制します
3. **サブエージェント** — 真の並列レイテンシ、専門能力、コンテキスト分離から恩恵を受けるタスクのための、並列・分離されたワーカー
4. **サンドボックス** — スレッドごとの分離ファイルシステム（スキル、ワークスペース、アップロード、出力）。プラグ可能な実行分離を備えます
5. **メモリ** — セッションをまたぐ永続的なユーザープロファイルとファクト。関連するときにプロンプトに注入されます
6. **ストリーミング** — Web UI、TUI、または IM チャネルにリアルタイムでレンダリングされる SSE イベント

基本理念は一言です：**スキルは教え、ミドルウェアは強制する。** 能力は `SKILL.md` ファイルで宣言されます。不変条件（書き込み前読み取り、トークン予算、ツールポリシー、ループ検出、安全終了）は、モデルが何をしようと、コード内で決定的に強制されます。

### 「チャットボット＋ツール」の問題

LLM とツールを包んだだけのチャットラッパーには、UniDeer が解決するために設計された 3 つの構造的な弱点があります：

- **強制力がない。** モデルは指示を無視できます。「答える前に必ず検索する」というプロンプトは提案に過ぎません。検索回数を数えて修正を注入するミドルウェアは保証です。
- **分離がない。** すべてのツール呼び出しがチャットと同じコンテキストで実行されるため、長い調査タスクが会話を汚染し、サブタスクを安全に並列実行できません。
- **状態の規律がない。** チェックポイント、圧縮、セッションをまたぐメモリがなければ、マルチターンのタスクは一貫性を失い、長時間のタスクはコンテキストウィンドウを吹き飛ばします。

UniDeer は、ステートマシンランタイム、強制パイプライン、サンドボックス化されたファイルシステムでこれら 3 つすべてに対処します。

### 設計原則

- **確率的よりも決定的に。** プロンプトは導きます。ミドルウェアは強制します。ゲート、カウンター、ポリシーはモデルの気まぐれではなく、メッセージ履歴とスレッド状態から導出されます。
- **プログレッシブローディング。** スキルは必要なときだけ読み込まれ、コンテキストウィンドウをスリムに保ちます。ツールは `tool_search` で発見され、関連するときにのみ昇格されます。
- **デフォルトで分離。** サブエージェントは親の履歴を見られません。サンドボックスパスはスレッドごと。メモリはユーザーとエージェントごと。実行は所有され、リースされます。
- **フェイルクローズ。** 競合する状態更新はエラーを発生させ、ツール認可は実行前にフィルタリングし、チェックポイント不変条件はデータベース層で部分一意インデックスによって強制されます。
- **運用可能。** 実行リース、孤児リカバリ、リクエストトレース相関、プラグ可能なトレーシング（Langfuse、LangSmith、Monocle）は、後付けではなく第一級市民です。

## 謝辞

UniDeer は、先行するチームとコミュニティの仕事なしには存在し得ませんでした。

- **[ByteDance](https://www.bytedance.com/)** — 元の DeerFlow プロジェクトとディープリサーチフレームワークの作成者。UniDeer はここからフォークされました。このプロジェクトは彼らのオープンソース基盤の上に構築されています。
- **[DeerFlow](https://github.com/bytedance/deer-flow)** — UniDeer がコミュニティフォークとして拠り所とする、上流のオープンソースプロジェクト（MIT ライセンス）。アーキテクチャ、スキルエコシステム、エンジニアリングに感謝します。
- **DeerFlow v1 のメンテナーとコントリビューター** — 元のディープリサーチフレームワーク（[1.x ブランチ](https://github.com/bytedance/deer-flow/tree/main-1.x) で保守）は、UniDeer が基づく 2.0 リライトの土台を築きました。
- **DeerFlow コミュニティ** — 上流プロジェクトを形作ったコントリビューター、テスター、ユーザーの皆さん。

UniDeer 自身の違い、最適化、追加点は[UniDeer と DeerFlow の違い](#unideer-と-deerflow-の違い)に記載されています。

## UniDeer と DeerFlow の違い

UniDeer はスーパーエージェントハーネスのビジョンを維持しつつ、エンジニアリングとプロダクトの方向性で分岐しています。今日重要となる違い：

| 領域 | DeerFlow（上流） | UniDeer（本プロジェクト） |
| --- | --- | --- |
| **リポジトリ** | `bytedance/deer-flow` | 独自のロードマップとリリースサイクルを持つ独立フォーク |
| **ミドルウェアパイプライン** | 広いキーワードトリガーのスキルゲートが、「形だけ」の未アクティブ会話にアクティベーションのナッジを注入 | **未アクティブスキルのファストエグジット**：スキルゲート（deep-research、system-design、startup-sketch など）は、スキルが明示的にスラッシュアクティベートされるか `skill_context` に読み込まれた場合にのみ発動。カジュアルなクエリはそのまま通過——プロンプトを汚染せず、ファーストトークンまでの時間を短縮 |
| **回答後修正** | Metacognition などのゲートが、回答を「修正」するために 2 回目の完全な LLM 生成をトリガーすることがある | **アドバイザリー修正**：回答後のナッジは即時の再生成を強制せず、次の自然なターンで発動。2 回目の LLM ラウンドトリップによるレイテンシスパイクを排除 |
| **サブエージェントの可観測性** | 折りたたまれたサブエージェントカードはステータスのみ表示 | **ライブランタイムメタデータ**：折りたたみカードに実効モデル名と累計トークン使用量を表示。各サブエージェント LLM 呼び出し後に更新され、リロード後も保持 |
| **セッション永続化** | セッションクッキーのみ | **「ログイン状態を保持」** ポリシー：統一セッションクッキーライフサイクル、`remember_me` 処理、デプロイ形態（HTTPS、ループバック、パブリック HTTP）に応じた Secure/Max-Age 戦略 |
| **メモリバックエンド** | DeerMem がデフォルト | DeerMem デフォルトに加え、**OpenViking HTTP バックエンド**を追加。リモート・クロスインスタンスのメモリ呼び出しをサポート |
| **認可** | デフォルトで無効 | **プラグ可能な認可 + 組み込み RBAC** プロバイダー。ロールごとのツール/ルート許可・拒否ポリシー |
| **トレース相関** | 基本 | X-Trace-ID 伝播に加え、`metadata.deerflow_trace_id` 相関を持つ Langfuse/LangSmith/Monocle トレーシング |
| **コードベース** | — | ハーネスパッケージ（`backend/packages/harness/deerflow/`）をここで保守。独自のテスト、不変条件（ハーネス/アプリのインポートファイアウォール）、ドキュメントを備える |

共有される DNA は残っています：スキル、サブエージェント、サンドボックス、メモリ、MCP、IM チャネルブリッジ。UniDeer の焦点は、**予測可能なレイテンシ**（無駄なトークンを出さない、予期せぬ再生成をしない）と**運用の深さ**（所有権、リース、データベースレベルの並行性、可観測性）です。

## アーキテクチャ概要

### サービストポロジー

標準的なデプロイでは、単一のコマンドまたは Docker Compose スタックから編成される 4 つの協調サービスが実行されます：

| サービス | ポート | 役割 |
| --- | --- | --- |
| **Nginx** | `2026` | 統合リバースプロキシエントリポイント。`/api/langgraph/*` を Gateway の組み込み LangGraph ランタイムにルーティングし、それ以外は Frontend にプロキシします。 |
| **Gateway API** | `8001` | FastAPI REST API に加え、組み込みの LangGraph ランタイム（`RunManager`、`run_agent()`、`StreamBridge`）。スタンドアロンの LangGraph サービスはありません——ランタイムは Gateway プロセス内にあります。 |
| **Frontend** | `3000` | Next.js 16 Web インターフェース（React 19、TypeScript、Tailwind CSS 4、pnpm）。 |
| **プロビジョナー** | `8002` | オプション——サンドボックスがプロビジョナー/Kubernetes モードに設定されている場合のみ起動。サンドボックス pod/VM のライフサイクルを管理します。 |

```
                    Browser / IM Client (Feishu, Slack, Telegram, WeChat, WeCom, DingTalk, GitHub, Discord)
                                       |
                                       v
                            Nginx (port 2026)
                     /api/langgraph/*          /, /workspace/*, /blog/*
                     |                        |
                     v                        v
            Gateway API (FastAPI :8001)   Frontend (Next.js :3000)
            + embedded LangGraph runtime
                     |
        +------------+------------+-----------+
        |            |            |           |
        v            v            v           v
   Sandbox      IM Channels  Provisioner   Persistence
   (E2B/Aio/    (8 bridges)   (:8002, K8s)  (SQLAlchemy +
    Local)                                  Alembic)
```

### ハーネスとアプリの依存ファイアウォール

バックエンドは、CI で強制される厳格な依存関係ルールを持つ 2 つのレイヤーに分かれています：

- `app.*`（FastAPI ホスト：ゲートウェイルーター、チャネルブリッジ、スケジューラー）は `deerflow.*` をインポート**できます**
- `packages/harness/deerflow/`（`deerflow.*` としてインポートされるハーネスパッケージ）は `app.*` をインポートしては**いけません**

これは `backend/tests/test_harness_boundary.py` によって強制され、CI で実行されます。ハーネスは公開可能で、アプリ非依存で、単独でテスト可能な状態を保ちます。2 つ目の不変条件は `make test-blocking-io` によって強制されます：非同期イベントループ上での同期ファイル/DB/ネットワーク I/O はゼロ——ブロッキング処理は `asyncio.to_thread` でオフロードする必要があります。

### 典型的なリクエストのエンドツーエンド

1. ユーザーが Frontend のコンポーザーにメッセージを入力します（オプションで音声文字起こしや AI ポリッシュ）。
2. `POST /api/threads/{id}/runs/stream` が SSE ストリーミングリクエストを開きます。
3. Gateway は認証（Better Auth クッキーセッション、CSRF、RBAC）を検証し、エージェント設定を解決し、LangGraph 実行を作成します。
4. `RunManager.run_agent()` はチェックポインターから `ThreadState` を読み込み、モデルを解決し、ミドルウェアチェーンを構築します。
5. リードエージェントノードが実行されます：メモリミドルウェアがユーザーコンテキストを注入し、スラッシュアクティベーション時にスキルアクティベーションが `SKILL.md` を読み込み、システムプロンプト（目標、スキル、ツール、メモリ）が組み立てられ、ツール定義付きでモデルが呼び出されます。
6. モデルがツールを呼び出した場合、組み込み / サンドボックス / コミュニティ / MCP ハンドラーにルーティングされ、結果がサニタイズされ、ループ検出が実行されます。
7. `task` ツールが呼び出された場合、サブエージェントエグゼキューターが分離されたコンテキストとスコープ化されたツールセットを持つ並列サブエージェントを生成します。それぞれが構造化された `TaskResult` を報告し、リードが統合します。
8. 実行後：メモリ抽出が新しいファクトを保存し、タイトルが生成され（最初のターン）、ワークスペース変更が計算され、目標が評価され、提案が生成されます。
9. `StreamBridge` は内部イベントを SSE イベント（`values`、`messages-tuple`、`custom`、`tasks`）に変換し、Frontend がリアルタイムにレンダリングします：アニメーションマークダウン、ステップタイムラインとトークン使用量付きのサブエージェントカード、ワークスペース変更 diff、TODO、目標ステータス、フォローアップ提案。

## コア機能

### スキルとツール

スキルは構造化された能力モジュールです——ワークフロー、ベストプラクティス、参考リソースを定義する `SKILL.md` ファイル。UniDeer には 30 以上の組み込みスキルが含まれ、独自のスキル追加、組み込みの置き換え、複合ワークフローへの組み合わせが可能です。

**スキルの仕組み：**

1. 各スキルは `skills/public/`（コミット済み）または `skills/custom/`（gitignore）配下の独自ディレクトリに置かれます。
2. `SKILL.md` ファイルがエントリポイントです——スキルがアクティブなときにエージェントが従う指示。
3. スキルは**プログレッシブローディング**——必要なときだけ読み込まれ、コンテキストウィンドウをスリムに保ちます。
4. スキルは `allowed-tools` を宣言して、アクティブなときにエージェントが使えるツールを制限できます（ベストエフォートの行動スコーピング）。
5. **スラッシュアクティベーション**：リクエスト先頭の `/skill-name` でそのターンのスキルをアクティブにします。
6. **SkillScan**：インストールされたスキルに対して決定的なセキュリティスキャナーが実行され、高信頼度の問題（秘密鍵、シェル実行パターン）をフラグします。

**アクティベーションゲート。** ドメイン固有のスキルゲート（deep-research、system-design、startup-sketch など）は、スキルがスレッド内で明示的にアクティブな場合にのみ発動します——`/skill-name` によるスラッシュアクティベーション、または `read_file` 読み込み後に `skill_context` に取り込まれた場合。スキル関連の単語を含むだけのカジュアルなクエリ（「なぜ…」「説明して…」「設計…」など）はそのまま通過します：隠れたアクティベーションナッジは注入されないため、カジュアルなターンがプロンプトを汚染したり、ファーストトークンまでの時間を遅くしたりしません。

**組み込みスキルには以下が含まれます：**

- 調査と分析：`deep-research`、`github-deep-research`、`data-analysis`、`academic-paper-review`、`systematic-literature-review`、`consulting-analysis`
- コンテンツ生成：`report-generation`、`ppt-generation`、`image-generation`、`video-generation`、`music-generation`、`podcast-generation`、`newsletter-generation`
- エンジニアリング：`frontend-design`、`web-design-guidelines`、`chart-visualization`、`code-documentation`、`system-design`、`bootstrap`
- プロダクトと要件：`business-requirement`、`product-requirements`、`software-requirements`、`startup-sketch`
- メタ：`skill-creator`、`skill-reviewer`、`find-skills`、`surprise-me`、`vercel-deploy-claimable`、`claude-to-deerflow`

スキルの `allowed-tools` ポリシーは、スキルが明示的にアクティベートされた後にのみ適用されます。有効化、宣伝、カスタムエージェントやサブエージェントの `skills` 許可リストへの掲載だけでは、エージェントの通常のツールセットは減りません。アクティブになると、ポリシーはモデル可視のツールスキーマとツール実行の両方をフィルタリングします。これはベストエフォートの行動スコーピングであり、ハードなセキュリティ境界ではありません。

### ミドルウェアパイプライン

リードエージェントグラフ（`make_lead_agent`）は、35 以上のミドルウェアステージ（ソースツリーには 60+ モジュール）からなるパイプラインを組み立て、すべてのモデル呼び出しとツール実行をラップします。これはハーネスの主要な拡張ポイントです。

おおよその順序で抜粋したステージ：

| ミドルウェア | 目的 |
| --- | --- |
| `InputSanitization` | 生入力の悪意あるシステムタグを中和 |
| `ToolOutputBudget` | 過大なツール出力をクランプしてコンテキストオーバーフローを防止 |
| `ToolResultSanitization` | リモートで取得した HTML/Web 結果をサニタイズ |
| `ThreadData` / `Uploads` | スレッド分離スコープをマウントし、アップロードファイルメタデータを注入 |
| `Sandbox` | サンドボックスコンテナまたはローカルコンテキストを取得 |
| `DanglingToolCall` | 割り込みリカバリ後に未完了のツール呼び出しをパッチ |
| `LLMErrorHandling` | プロバイダーエラーを回復可能なターンに正規化 |
| `SandboxAudit` | bash コマンドの安全でないパターンを AST 検査 |
| `ReadBeforeWrite` | ファイル書き込み前に暗号化 SHA ハッシュスタンプゲートを強制 |
| `ToolProgress` | ツール停滞を検出するステートマシン（ACTIVE から WARNED から BLOCKED） |
| `SkillActivation` / `SkillToolPolicy` | `SKILL.md` コンテキストをバインドし、`allowed-tools` を強制 |
| `Metacognition` | 複雑なプロンプトに対する思考優先の強制（回答前；回答後はアドバイザリー） |
| `Planner` | マルチステップ変更に対する「計画なしに編集なし」ルール |
| `EmojiGate` | 生成コード/設定を絵文字なしに保つ Unicode スキャナー |
| `Summarization` / `TokenBudget` | 高トークン水位でのコンテキスト圧縮 |
| `TodoList` / `Title` | プランモードのタストラッキングと最初のターン後の自動タイトル |
| `Memory` | 実行前に長期メモリを注入し、実行後に新しいファクトを抽出 |
| `LoopDetection` | 繰り返される同一ツール呼び出しループをハードストップ |
| `TerminalResponse` | 空のアシスタント応答を再試行し、サイレント失敗を防止 |
| `Safety / ModelLengthFinishReason` | プロバイダーコンテンツフィルターと最大トークン制限を処理 |
| `Clarification`（最後） | `ask_clarification` をインターセプトし、`Command(goto=END)` を発行 |

同じチェーン（リードエージェント固有のステージを除く）がサブエージェントにも適用されるため、委任されたタスクは親と同じ不変条件に支配されます。

### サブエージェント

サブエージェントは最適化であり、複雑なリクエストへのデフォルト応答ではありません。

リードエージェントは、委任に明確な正味の利益がある場合（真の並列レイテンシ、専門能力、コンテキスト分離）に、その場でサブエージェントを生成します——それぞれが独自のスコープ化されたコンテキスト、ツール、終了条件を持ちます。相互依存するスコープと重複する副作用は並列ディスパッチから除外します。サブエージェントは構造化された結果を報告し、リードが検証して統合します。

**実行モデル。** サブエージェントエグゼキューターはスレッドプール + asyncio のハイブリッドです：コンテキスト変数は親から正しく伝播され、各サブエージェントは独自の分離イベントループで実行され、ライフサイクル状態は厳格なステートマシンに従います：`PENDING` から `RUNNING` へ、そして `COMPLETED` / `FAILED` / `CANCELLED` / `TIMED_OUT` へ。ガードレール上限（`token_capped`、`turn_capped`、`loop_capped`）は部分出力を保持しつつ実行を早期終了させ、リードは「完了」と「上限到達」を区別できます。

**並行性制限。** `SubagentLimitMiddleware` は並行委任（デフォルト 3、設定可能 1-4）と実行ごとの委任総数（デフォルト 6、最大 50）をクランプします。

**構造化契約。** サブエージェントの結果は、固定された契約として `ToolMessage.additional_kwargs` に載せられます：ステータス、停止理由、エラー、完全な結果の SHA-256 ダイジェスト、実効モデル名、累計トークン使用量。列挙値は `contracts/subagent_status_contract.json` を介して Python と TypeScript で共有され、契約テストが両者を固定するため、フロントエンドとバックエンドがドリフトすることはありません。

**ライブランタイムメタデータ。** 折りたたまれたサブエージェントカードは実効モデルを表示し、プロバイダーが使用量メタデータを返す場合は累計トークン合計を表示します。各サブエージェント LLM 呼び出しの完了後に更新され、リロード後も保持されます。並行サブエージェントは `task_id` をキーに独立した合計を維持します。使用量を省略するプロバイダーは明示的な「利用不可」状態を表示し、偽のゼロは決して表示しません。

独立した読み取り専用調査は、ウォールクロックの節約が重複する発見と統合コストを上回る場合に並行実行できます。共有ファイルと順次テストフィードバックを伴うリポジトリリファクタリングはリードエージェントに残ります。`max_concurrent_subagents` が 1 の場合、並列およびマルチバッチルーティングガイダンスは無効化され、委任は実質的な専門能力またはコンテキスト分離の利益がある場合のみ利用可能です。

### サンドボックスとファイルシステム

各タスクは、完全なファイルシステムビュー（スキル、ワークスペース、アップロード、出力）を持つ独自の実行環境を取得します。

```
/mnt/user-data/
├── uploads/          # your files
├── workspace/        # agents' working directory
└── outputs/          # final deliverables
```

**プロバイダー：**

| プロバイダー | 説明 |
| --- | --- |
| `E2BSandboxProvider` | VM 分離、ウォームプール、バースト、マルチワーカー展開の Redis 所有権を備えたリモート E2B サンドボックス |
| `AioSandboxProvider` | コンテナベースの分離（Docker） |
| `LocalSandboxProvider` | スレッドごとのディレクトリを持つホストファイルシステム。ホスト bash はデフォルトで無効 |

**主な機能：**

- パスセキュリティポリシーと環境変数ポリシーを備えたスレッドごとのディレクトリ分離
- 同じパスへの並行読み書きを直列化するファイル操作ロック
- **書き込み前読み取りの強制**：`read_file` はファイルの現在の内容の SHA-256 ハッシュをメッセージにスタンプします。既存ファイルへの `write_file` / `str_replace` は、ディスク上のハッシュがスタンプと一致しない限り決定的にブロックされます。書き込みは以前の読み取りを無効化するため、連続する変更の間に再読み取りが強制されます。
- **ワークスペース変更トラッキング**：実行後、`workspace` と `outputs` の変更ファイルの diff 概要が記録され、UI に「files changed」バッジとテキスト diff として表示されます。アップロードは除外されます（ユーザー入力だからです）。
- 画像処理：base64 画像はビジョンモデルが消費した後、チェックポイントから削除され、ペイロードの重複を防ぎます。
- 組み込み `grep` ツールによるサンドボックスファイルの検索。

### コンテキストエンジニアリング

- **分離されたサブエージェントコンテキスト** — サブエージェントは親や兄弟の履歴を見られません
- **要約** — 完了したサブタスクは圧縮され、中間結果はファイルシステムにオフロードされ、トークン制限内に収まるようにコンテキストが圧縮されます
- **厳格なツール呼び出しリカバリ** — ぶら下がったツール呼び出しは、次のモデル呼び出しの前にプレースホルダー結果でパッチされ、厳格な推論モデルが不正な履歴で失敗するのを防ぎます
- **可視のツール実行完了** — 空のツール後最終応答は一度再試行され、サイレント成功ではなく可視エラーとして提示されます
- **手動圧縮** — コンポーザーの `/compact` は、チャット全体を表示したまま古いコンテキストを要約します
- **セッション目標** — `/goal <条件>` はスレッドスコープの完了条件を設定します。ランタイムは実行ごとに会話を目標に対して評価し、満たされるかクリアされるまで隠れた継続（安全上限 8 回）を注入します

### 長期メモリ

ユーザープロファイル、好み、蓄積された知識の、セッションをまたぐ永続的なメモリ。

**ストレージアーキテクチャ：**

```
{deerflow_home}/memory/
├── users/{user_id}/
│   ├── memory.json              # user profile + history summaries (JSON)
│   └── agents/{agent_name}/
│       └── facts/
│           ├── ab/cdef123...md  # individual fact (Markdown, sharded by SHA-256)
│           └── ...
```

- ファクトは正規の Markdown ファイルで、`SHA-256(fact_id)` の最初の 2 つの 16 進文字でシャーディングされます
- ジャーナル書き込みがサイレントな更新ロストを防ぎます。共有ユーザーロックと楽観的リビジョンが並行アクセスを保護します
- 検索はデフォルトでスコープ付き SQLite FTS5/BM25 アダプターを使用し、ローカル部分文字列フォールバック付き。派生インデックスは再構築可能で、破損したインデックスは自動的に再作成されます
- レガシー `memory.json` ファクトは最初の読み取り時に自動移行されます

**バックエンド：**

- **DeerMem**（デフォルト）— ファイルバックアップ、スコープ認識、保存前に各候補ファクトをスコープ、耐久性、権威で分類する抽出書き込みゲート付き。永続的で記述的なユーザーレベルのファクトのみが保存されます。現在のスレッド制約と一度きりの許可は会話状態に残ります。
- **OpenViking**（オプション）— 独立した OpenViking サーバーに HTTP で接続し、リモート・クロスインスタンスの呼び出しをサポート。境界付き送信ウォーターマークとジッター付きリトライが、再試行時の重複コミットを防ぎます。

メモリ注入は操作モード（`middleware` と `tool`）で設定可能で、`memory.injection_enabled: false` はブロック全体を無効化します。

### MCP とモデルファクトリー

UniDeer は **Model Context Protocol** をサポートし、stdio または HTTP 経由で外部ツールサーバーに接続します。ツールスキーマキャッシュ、MCP ルーティングミドルウェア、MCP 由来ツールのツール注釈を備えます。

モデルファクトリーはプロバイダー非依存です：

- OpenAI および OpenAI 互換 API（`langchain_openai:ChatOpenAI`）
- vLLM（セルフホスト、`chat_template_kwargs.enable_thinking` による思考/推論サポート）
- OpenAI Codex CLI（`gpt-5.4` クラス）と Anthropic Claude（OAuth または API キー）
- Huawei MindIE、および推論用にパッチされたプロバイダー（DeepSeek、MiniMax、StepFun、MiMo）

思考/推論サポート（`supports_thinking`、`supports_reasoning_effort`）、ビジョンモデル、Responses API（`output_version: responses/v1`）はすべて第一級市民です。資格情報は資格情報ローダーを介して環境変数から読み込まれます。

### ツールカタログ

**組み込みツール** — `task`（サブエージェントを生成）、`tool_search`（説明でツールを発見）、`ask_clarification`（ユーザー入力を待つ）、`view_image`、`present_file`、`list_uploaded_files`、`review_skill_package`、`setup_agent` / `update_agent`、`invoke_acp_agent`。

**コミュニティツール** — `web_search`、`web_fetch`、`web_capture`、`image_search`（プロバイダー設定可能）。

**サンドボックスツール** — `bash`、`ls`、`read_file`（行範囲対応）、`write_file`、`str_replace`。

**ブラウザツール**（オプションの追加）— `browser_navigate`、`browser_snapshot`、`browser_click`、`browser_type`、`browser_get_text`、`browser_back`、`browser_screenshot`、`browser_close`。Playwright 駆動、SSRF スクリーニング付き。デフォルトで無効。

**認可。** `authorization.enabled` を有効にすると、プラグ可能な `AuthorizationProvider` がツールをモデルや遅延ツールカタログに到達する前にフィルタリングし、ビジネスツール実行のたびに再度チェックします。組み込み RBAC プロバイダーはロールごとの `tools` と `routes` の許可・拒否ポリシーをサポートします。

## ランタイムと信頼性

### 実行の所有権、リース、リカバリ

すべての実行には所有権があります。ランタイムは一意のワーカー ID（`hostname:hex_uuid`）を割り当て、各実行にリースをスタンプし、所有権を runs テーブルに永続化します。Gateway が再起動した場合、またはワーカーが実行が永続的な最終状態に達する前に到達不能になった場合、実行は明確な停止理由を持つ孤児としてリカバリされます：

- `"Gateway restarted before this run reached a durable final state."`
- `"Run lease expired - owning worker is unreachable."`

リース期限切れ検出、起動時孤児リカバリ、マルチワーカー実行所有権は、SQLite（ローカル）と Postgres（デプロイ）の両方でサポートされています。ステータス確定時の一時的な SQLite ロック競合は制限付きバックオフで再試行され、ドライバー固有の一意制約シグナル（Postgres `23505`、SQLite 制約コード）はロケール依存のエラーテキストに頼らず検出されます。

### チェックポインティング

スレッド状態はすべてのステップの後にチェックポイントされ、実行の再開やブランチが可能です。ランタイムは上流の LangGraph チェックポイント機構の互換性パッチを同梱しています（例：full-to-delta 移行スレッドで書き込みが失われる `InMemorySaver` の修正）。検証済みの LangGraph バージョンに固定され、上流が修正した場合は自動的に停止します。チェックポイントチャネルモードとスナップショット頻度はデプロイごとに設定可能です。

### データベースレベルの並行性インバリアント

並行性はメモリ内フラグではなくデータベースによって管理されます。部分一意インデックスが重要な不変条件を強制します：

| インデックス | 不変条件 |
| --- | --- |
| `uq_runs_thread_active` | スレッドごとに最大 1 つの pending/running 実行（`WHERE status IN ('pending','running')`） |
| `uq_scheduled_task_run_active` | スケジュールタスクごとに最大 1 つのアクティブ実行（`WHERE status IN ('queued','running')`） |
| `uq_channel_connection_active_identity` | 外部 IM アイデンティティの単一アクティブ所有者転送（`WHERE status != 'revoked'`） |

移行には重複排除の事前ステップが含まれているため、すでに不変条件に違反しているデータベース（現場のデータベース、修正前のマルチワーカーデプロイ）でもインデックスを構築できます。競合で負けた書き込み側は型付き競合（例：`ActiveScheduledRunConflict`）として表面化し、アクティブ実行と重複するスケジュールディスパッチはアクティブスロットを占有しない終端 `skipped` トゥームストーンを記録します。

## クイックスタート

### 前提条件

- Python 3.12+ と `uv`
- Node.js 22+ と pnpm 10
- `nginx`（`make dev` の統合ローカルエンドポイントに必要）
- Docker（オプション、コンテナ化デプロイ用）

`make check` を実行してツールチェーンを確認します。

### 設定

```bash
git clone https://github.com/bytedance/deer-flow.git
cd deer-flow
```

> 上記のクローン URL は上流リポジトリを指しています。UniDeer の場合は、受け取ったフォーク URL からクローンしてください。

1. 依存関係をインストール：`make install`（ターゲットの実装に従い、バックエンド→フロントエンドの順）
2. セットアップウィザードを実行：

```bash
make setup
```

ウィザードは、LLM プロバイダーの選択、オプションの Web 検索、サンドボックスモード、bash アクセス、ファイル書き込みツールなどの実行/安全設定を案内します。最小限の `config.yaml` を生成し、キーを `.env` に書き込みます。約 2 分かかります。

いつでも `make doctor` を実行してセットアップを検証し、実行可能な修正ヒントを得られます。ローカルセットアップやランタイムの問題で GitHub issue を開く場合は、`make support-bundle` を実行してください——匿名化された issue サマリー、AI 支援の issue ドラフト、`.deer-flow/support-bundles/` の下のオプションの証拠 ZIP を書き出します。

**設定ファイル：**

- `config.yaml`（gitignore）— メインのアプリ設定：モデル、サンドボックス、ツール、チャネル、スケジューラー、ロギング、トレーシング
- `extensions_config.json`（gitignore）— MCP サーバーとスキル定義
- `config.example.yaml` / `extensions_config.example.json` — コピー用テンプレート

`make config-upgrade` を使用して、`config.example.yaml` の新しいフィールドを既存の `config.yaml` にマージし、ローカル設定を失わずに済ませます。

**モデル**は `config.yaml` の `models:` で設定します。各エントリはプロバイダークラス、モデル ID、環境変数による資格情報を指定します：

```yaml
models:
  - name: gpt-4o
    display_name: GPT-4o
    use: langchain_openai:ChatOpenAI
    model: gpt-4o
    api_key: $OPENAI_API_KEY
  - name: qwen3-32b-vllm
    display_name: Qwen3 32B (vLLM)
    use: deerflow.models.vllm_provider:VllmChatModel
    model: Qwen/Qwen3-32B
    api_key: $VLLM_API_KEY
    base_url: http://localhost:8000/v1
    supports_thinking: true
```

**環境変数**（パスとランタイム状態）：

- `UNI_DEER_PROJECT_ROOT` — 明示的なプロジェクトルート
- `UNI_DEER_CONFIG_PATH` — 特定の設定ファイルを指定
- `UNI_DEER_HOME` — ランタイム状態の場所（デフォルトはプロジェクトルートの `.deer-flow`）
- `UNI_DEER_SKILLS_PATH` — スキルディレクトリ（デフォルトはプロジェクトルートの `skills/`）

### アプリケーションの起動

**オプション 1：Docker（推奨）**

```bash
make docker-start
```

`config.yaml` からのモード認識起動。統合エンドポイントは `http://localhost:2026`。他のターゲット：`make docker-stop`、`make docker-logs`、`make docker-logs-gateway`、`make docker-logs-frontend`、`make docker-logs-redis`。

**オプション 2：ローカル開発**

```bash
make dev
```

ホットリロード付きで 3 つのサービスを起動します：

- Gateway API（FastAPI、ポート 8001、組み込み LangGraph ランタイム）
- Frontend（Next.js、ポート 3000）
- Nginx（ポート 2026 — 統合エントリポイント）

`make stop` で全て停止します。ログは `logs/gateway.log`、`logs/frontend.log`、`logs/nginx.log` にあります。Windows では、ローカルフローを Git Bash から実行してください（ネイティブの `cmd.exe`/PowerShell は bash ベースのサービススクリプトをサポートしていません）。

**バックエンド開発コマンド**（`backend/` 内）：

```bash
make dev                # FastAPI Gateway with reload (port 8001)
make test               # offline unit tests
make test-blocking-io   # strict blocking-IO runtime gate
make lint               # ruff check
make format             # ruff format
make migrate-rev MSG="" # autogenerate an Alembic migration
```

**フロントエンド開発コマンド**（`frontend/` 内）：

```bash
pnpm dev                # Next.js Turbopack dev server (port 3000)
pnpm lint               # ESLint
pnpm typecheck          # TypeScript check
pnpm test               # unit tests
pnpm test:e2e           # Playwright E2E tests
```

### 起動モード

`config.yaml` はモード認識起動をサポートします：

| モード | 説明 |
| --- | --- |
| `flash` | 高速応答、最小限の推論 |
| `standard` | 速度と深さのバランス |
| `pro` | 明示的な推論を伴うプランニングモード |
| `ultra` | 完全なサブエージェントオーケストレーション |

## アドバンスト

### サンドボックスプロバイダー

**E2B** はデフォルトのオーバーフローポリシーとして `wait` を使用します：`acquire_timeout` まで待機し、エージェントターンを失敗させます（UniDeer は自動的に再試行しません。クライアントは構造化エラーを使用して再試行をスケジュールできます）。`burst` と `burst_limit` で限定的な追加 VM を許可します。`reject` はエラーを返す前にウォーム VM を 1 つ削除できます。Redis 所有権では、`replicas` は 1 つの容量ハッシュを介してワーカー間で共有されるデプロイ全体のハードリミットです。不一致のワーカーはフェイルクローズします。

**Aio** は隔離された Docker コンテナ内でシェル実行を行い、スレッドデータマウントをバックエンドから検出します（ローカルコンテナはマウントされたゲートウェイディレクトリを使用し、リモート/プロビジョナーサンドボックスは明示的な同期でアップロードを受け取ります）。

**Local** はファイルツールをホスト上のスレッドごとのディレクトリにマップしますが、ホスト `bash` は安全な分離境界ではないためデフォルトで無効です。完全に信頼できるローカルワークフローのみで再有効化してください。ホスト bash コマンドにはウォールクロックタイムアウトがあります。

### IM チャネル

UniDeer は外部メッセージングプラットフォームにブリッジします：**Feishu、Slack、Telegram、Discord、DingTalk、WeChat、WeCom、GitHub**。すべてのチャネルは Gateway 実行ライフサイクルを通る共通の実行パスを共有します：

- 各チャネルはユーザーメッセージを受信し、スレッド実行に変換し、応答をストリーミングして返します
- セッション管理（アシスタント ID、再帰制限、思考モード）はチャネルごとに設定可能
- メッセージバス、チャネルごとの実行ポリシー、接続アイデンティティリンクが 8 つのブリッジを統合します
- **単一アクティブ所有者転送**：外部アイデンティティは `(provider, external_account_id, workspace_id)` でキー付けされます。最新の成功したバインドが勝ち、`uq_channel_connection_active_identity` 部分一意インデックスによってレースフリーに強制されます
- インバウンド再配信の重複排除、サンドボックスへのファイル添付ステージング、成果物配信（outputs のみ——他のパスは流出防止のため拒否）

### 認可と RBAC

高度なデプロイでは、`config.yaml` の `authorization.enabled` でプラグ可能な認可を有効にできます。設定された `AuthorizationProvider` は、ツールがモデルまたは遅延ツールカタログに到達する前に拒否されたツールをフィルタリングし、ビジネスツール実行のたびに同じプロバイダーが再度チェックされます。Gateway の `threads:*` と `runs:*` ルート権限は同じプロバイダーから派生し、既存の所有者チェックと管理者専用管理ゲートは引き続き有効です。組み込み RBAC プロバイダーはロールごとの `tools` と `routes` の許可・拒否ポリシーをサポートし、`default_role` が設定されたロールを指すことを検証します。デフォルトで無効です。

### トレーシングと可観測性

- **リクエストトレース相関**：すべての Gateway HTTP 応答に `X-Trace-Id` が含まれます。ログには `trace_id` が含まれます
- **Langfuse**：トレースには `X-Trace-Id` に一致する `metadata.deerflow_trace_id` が含まれます。`UNI_DEER_ENV`（または `ENVIRONMENT`）を設定して、デプロイ環境ごとにトレースをタグ付けします
- **LangSmith と Monocle**：プラグ可能なトレーシングプロバイダー
- トレーシングコールバックはグラフ呼び出しのルートでアタッチされるため、スパンが重複しません。この不変条件はコードベースに明示的に文書化されています

### スケジュールタスク

Web UI または Gateway API から定期的なエージェント実行を設定します。バックグラウンドスケジューラーが各タスクを cron スケジュールでディスパッチし、以下を備えます：

- データベース強制の「タスクごとに最大 1 つのアクティブ実行」セマンティクス（`uq_scheduled_task_run_active`）
- アクティブ実行と重複したディスパッチの `skipped` トゥームストーン（アクティブスロットを決して占有しない）
- 手動トリガーがポーラーと競合しても、高速パスと同じ結果に収束（手動：409 競合、スケジュール：`skipped`）

### プロビジョナー（Kubernetes）

オプションのプロビジョナーサービス（ポート 8002）は、Kubernetes ベースのデプロイのサンドボックスインフラストラクチャを管理します：サンドボックス pod/VM をオンデマンドで割り当て、高速取得のためのウォームプールを維持し、完全なライフサイクル（作成、ヘルスチェック、破棄）を処理します。サンドボックスがプロビジョナー/K8s モードに設定されている場合のみ起動されます。E2B/Aio プロバイダーを使用するローカルおよび Docker Compose デプロイには不要です。

## 組み込み Python クライアント

UniDeer インスタンスとプログラム的にやり取りします——Web UI は不要です：

```python
from deerflow.client import DeerFlowClient

client = DeerFlowClient(base_url="http://localhost:8001")

# Stream a turn
for event in client.stream("thread-id", "your prompt"):
    print(event)

# Create a thread
thread = client.create_thread(agent="lead_agent")
```

クライアントはスレッド作成、メッセージストリーミング（UI と同じ SSE モード）、メモリ管理、ファイルアップロード、エージェント設定をサポートします。`backend/` で `make test-live` を実行してライブ API テストを行います。

## ターミナルワークベンチ（TUI）

Web UI なしで UniDeer とやり取りするためのターミナルインターフェース——CLI から新しいスレッド、ストリーミング応答、目標、スキルコマンド。`deerflow` CLI コマンドで起動します。TTY 以外では、スクリプト化のためにヘッドレス `--print` / `--json` 出力に退化します。

## デプロイ

### ローカル開発

```bash
make dev       # Gateway (8001) + Frontend (3000) + Nginx (2026)
make stop      # stop everything
```

### Docker

```bash
make docker-start   # mode-aware development stack from config.yaml (localhost:2026)
make up             # production compose (localhost:2026)
make down           # stop and remove production containers
```

### Kubernetes

Kubernetes デプロイ用の Helm チャートが `deploy/helm/deer-flow/` にあります。プロビジョナーがサンドボックスインフラストラクチャを管理します。

## セキュリティ

UniDeer は設計上、エージェントに実際のファイルシステムと実行能力を与えます。デプロイは特権インフラストラクチャとして扱う必要があります：

- **不適切なデプロイはセキュリティリスクをもたらす可能性があります。** ゲートウェイ管理者は実質的にホスト上のコード実行と同等です。
- ローカルサンドボックスはデフォルトでホスト bash を無効にします。完全に信頼できるローカルワークフローのみで再有効化してください。
- ブラウザ制御は、信頼できるデバッグ以外では `headless: true` と `allow_private_addresses: false` を維持してください。`cdp_url` で既存の Chrome にアタッチすると SSRF ガードを強制できず、`allow_unguarded_cdp: true` で明示的にリスクを認めない限りフェイルクローズします。
- `config.yaml` と `extensions_config.json` を信頼できるオペレーター管理ファイルとして扱ってください：ミドルウェア、ツール、モデル、サンドボックス、ガードレール、MCP 宣言はすべてコード実行です。
- 認証は HttpOnly クッキー、CSRF 保護、プラグ可能な RBAC を使用します。「ログイン状態を保持」ポリシーはパブリック HTTP ではセッションクッキーに降格し、HTTPS またはループバックでのみ Secure + Max-Age を使用します。

## ドキュメント

- [アーキテクチャ](docs/ARCHITECTURE.md) — サービストポロジー、全 8 レイヤー、データフロー、リポジトリマップ、用語集
- [コンテキストガイド](context.md) — コーディングエージェント向けのシステムアーキテクチャとエージェントコンテキスト
- [計画と RFC](docs/plans/) — 認可、トレーシング、メモリなど
- [コントリビューション](CONTRIBUTING.md) — 開発環境とワークフロー
- [インストール](Install.md) — ワンラインエージェントセットアップ手順

## コントリビューション

開発環境のセットアップ、必要なコマンド順序、検証の期待値については [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。変更を送信する前に：

- バックエンド：`cd backend && make lint && make test`（CI 同等：`uv sync --group dev`、次に lint、次に test）
- フロントエンド（変更がある場合）：`cd frontend && pnpm lint && pnpm typecheck`。プロダクションビルドには `BETTER_AUTH_SECRET` を設定
- ハーネス/アプリのインポートファイアウォールを壊さない（`tests/test_harness_boundary.py`）
- 非同期イベントループをブロッキング I/O フリーに保つ（`make test-blocking-io`）
- 機能を変更する場合はドキュメントを更新（`README.md`）、アーキテクチャ/ミドルウェアを変更する場合は（`AGENTS.md`）

## ライセンス

UniDeer は **MIT ライセンス** で配布されます——[LICENSE](LICENSE) を参照してください。DeerFlow（同じく MIT）のフォークとして、上流プロジェクトから派生した部分の元の著作権と帰属は ByteDance と DeerFlow コントリビューターに帰属します。
