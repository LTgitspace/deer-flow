# UniDeer - 2.0

[English](./README.md) | [中文](./README_zh.md) | [日本語](./README_ja.md) | Français | [Русский](./README_ru.md)

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

UniDeer (**D**eep **E**xploration and **E**fficient **R**esearch **Flow**) est un **super agent harness** open source construit sur **LangGraph**. Il orchestre des **sous-agents**, la **mémoire à long terme** et l'**exécution sandboxée** pour traiter des tâches complexes en plusieurs étapes — le tout propulsé par des **skills extensibles**.

UniDeer est un **fork communautaire de [DeerFlow](https://github.com/bytedance/deer-flow), créé par [ByteDance](https://www.bytedance.com/)** (v2.0+), et a évolué en un projet distinct avec sa propre direction d'ingénierie. Il partage la lignée du deep-research et une grande partie de l'architecture d'origine ; le code, le pipeline de middlewares et le comportement du runtime ont été retravaillés. Voir [Différences entre UniDeer et DeerFlow](#différences-entre-unideer-et-deerflow) et [Remerciements](#remerciements).

> **Note sur la lignée :** DeerFlow 2.0 était une réécriture complète qui ne partageait aucun code avec la v1. UniDeer s'appuie sur cette base 2.0 et continue à partir de là. Le framework deep-research v1 d'origine reste maintenu en amont sur la [branche 1.x](https://github.com/bytedance/deer-flow/tree/main-1.x).

---

## Table des matières

- [Pourquoi UniDeer](#pourquoi-unideer)
  - [Le problème du « chatbot plus outils »](#le-problème-du-chatbot-plus-outils)
  - [Principes de conception](#principes-de-conception)
- [Remerciements](#remerciements)
- [Différences entre UniDeer et DeerFlow](#différences-entre-unideer-et-deerflow)
- [Vue d'ensemble de l'architecture](#vue-densemble-de-larchitecture)
  - [Topologie des services](#topologie-des-services)
  - [Le pare-feu de dépendances harness / app](#le-pare-feu-de-dépendances-harness--app)
  - [Une requête typique, de bout en bout](#une-requête-typique-de-bout-en-bout)
- [Fonctionnalités principales](#fonctionnalités-principales)
  - [Skills et outils](#skills-et-outils)
  - [Le pipeline de middlewares](#le-pipeline-de-middlewares)
  - [Sous-agents](#sous-agents)
  - [Sandbox et système de fichiers](#sandbox-et-système-de-fichiers)
  - [Ingénierie du contexte](#ingénierie-du-contexte)
  - [Mémoire à long terme](#mémoire-à-long-terme)
  - [MCP et fabrique de modèles](#mcp-et-fabrique-de-modèles)
  - [Catalogue d'outils](#catalogue-doutils)
- [Runtime et fiabilité](#runtime-et-fiabilité)
  - [Propriété des exécutions, baux et récupération](#propriété-des-exécutions-baux-et-récupération)
  - [Points de contrôle](#points-de-contrôle)
  - [Invariants de concurrence au niveau base de données](#invariants-de-concurrence-au-niveau-base-de-données)
- [Démarrage rapide](#démarrage-rapide)
  - [Prérequis](#prérequis)
  - [Configuration](#configuration)
  - [Lancement de l'application](#lancement-de-lapplication)
  - [Modes de démarrage](#modes-de-démarrage)
- [Avancé](#avancé)
  - [Fournisseurs de sandbox](#fournisseurs-de-sandbox)
  - [Canaux IM](#canaux-im)
  - [Autorisation et RBAC](#autorisation-et-rbac)
  - [Traçage et observabilité](#traçage-et-observabilité)
  - [Tâches planifiées](#tâches-planifiées)
  - [Provisioner (Kubernetes)](#provisioner-kubernetes)
- [Client Python embarqué](#client-python-embarqué)
- [Terminal Workbench (TUI)](#terminal-workbench-tui)
- [Déploiement](#déploiement)
  - [Développement local](#développement-local)
  - [Docker](#docker)
  - [Kubernetes](#kubernetes)
- [Sécurité](#sécurité)
- [Documentation](#documentation)
- [Contribution](#contribution)
- [Licence](#licence)

---

## Pourquoi UniDeer

La plupart des outils « agent IA » ne sont que des interfaces de chat avec un outil de recherche ajouté. UniDeer est un **harness** : un runtime structuré qui transforme une génération LLM stochastique en un pipeline d'exécution déterministe, gouverné par une machine à états.

Une requête traverse :

1. **L'agent principal (lead agent)** — planifie le tour, décide s'il délègue et synthétise la réponse finale
2. **La chaîne de middlewares** — un pipeline de plus de 35 intercepteurs composables qui appliquent skills, budgets, sécurité et politiques d'outils avant et après chaque appel de modèle
3. **Les sous-agents** — des travailleurs parallèles et isolés pour les tâches qui bénéficient d'une latence parallèle réelle, d'une capacité spécialisée ou d'une isolation du contexte
4. **La sandbox** — un système de fichiers isolé par thread (skills, workspace, uploads, outputs), avec isolation d'exécution pluggable
5. **La mémoire** — profils utilisateur et faits persistants entre sessions, injectés dans le prompt quand c'est pertinent
6. **Le streaming** — des événements SSE rendus en direct dans l'interface web, la TUI ou les canaux IM

La philosophie directrice tient en une phrase : **les skills enseignent, les middlewares appliquent.** Les capacités sont déclarées dans les fichiers `SKILL.md` ; les invariants — lecture avant écriture, budgets de tokens, politiques d'outils, détection de boucles, terminaisons de sécurité — sont appliqués dans le code, de manière déterministe, quelle que soit la décision du modèle.

### Le problème du « chatbot plus outils »

Un simple wrapper de chat autour d'un LLM avec des outils présente trois faiblesses structurelles qu'UniDeer est conçu pour corriger :

- **Pas de force d'application.** Un modèle peut ignorer les instructions. Un prompt qui dit « cherchez toujours avant de répondre » est une suggestion ; un middleware qui compte les recherches et injecte une correction est une garantie.
- **Pas d'isolation.** Chaque appel d'outil s'exécute dans le même contexte que le chat, donc une longue tâche de recherche pollue la conversation et une sous-tâche ne peut pas s'exécuter en parallèle en toute sécurité.
- **Pas de discipline d'état.** Sans points de contrôle, compaction et mémoire inter-sessions, une tâche multi-tours perd sa cohérence et une tâche de plusieurs heures fait exploser la fenêtre de contexte.

UniDeer résout ces trois problèmes avec un runtime à machine à états, un pipeline d'application et un système de fichiers sandboxé.

### Principes de conception

- **Déterministe plutôt que stochastique.** Les prompts guident ; les middlewares appliquent. Les portes, compteurs et politiques sont dérivés de l'historique des messages et de l'état du thread, pas des caprices du modèle.
- **Chargement progressif.** Les skills ne sont chargés que lorsque nécessaire, gardant la fenêtre de contexte légère. Les outils sont découverts via `tool_search` et promus seulement quand c'est pertinent.
- **Isolation par défaut.** Les sous-agents ne voient pas l'historique du parent ; les chemins de sandbox sont par thread ; la mémoire est par utilisateur et par agent ; les exécutions sont possédées et louées.
- **Échec fermé.** Les mises à jour d'état conflictuelles lèvent une erreur, l'autorisation d'outil filtre avant l'exécution, et les invariants de points de contrôle sont appliqués au niveau de la base de données avec des index uniques partiels.
- **Exploitable.** Baux d'exécution, récupération des orphelins, corrélation des traces de requêtes et traçage pluggable (Langfuse, LangSmith, Monocle) sont des citoyens de première classe, pas des ajouts après coup.

## Remerciements

UniDeer n'existerait pas sans le travail des équipes et des communautés qui l'ont précédé.

- **[ByteDance](https://www.bytedance.com/)** — créateur du projet DeerFlow original et du framework deep-research dont UniDeer est issu. Ce projet s'appuie sur leur fondation open source.
- **[DeerFlow](https://github.com/bytedance/deer-flow)** — le projet open source amont (licence MIT) dont UniDeer est un fork communautaire. Nous sommes reconnaissants pour l'architecture, l'écosystème de skills et l'ingénierie qui ont rendu cela possible.
- **Mainteneurs et contributeurs de DeerFlow v1** — le framework Deep Research original (maintenu sur la [branche 1.x](https://github.com/bytedance/deer-flow/tree/main-1.x)) a posé les fondations de la réécriture 2.0 sur laquelle UniDeer s'appuie.
- **La communauté DeerFlow** — contributeurs, testeurs et utilisateurs qui ont façonné le projet amont.

Les différences, optimisations et ajouts propres à UniDeer sont documentés dans [Différences entre UniDeer et DeerFlow](#différences-entre-unideer-et-deerflow).

## Différences entre UniDeer et DeerFlow

UniDeer conserve la vision du super agent harness mais diverge dans la direction d'ingénierie et de produit. Les différences qui comptent aujourd'hui :

| Domaine | DeerFlow (amont) | UniDeer (ce projet) |
| --- | --- | --- |
| **Dépôt** | `bytedance/deer-flow` | Fork indépendant avec sa propre feuille de route et son propre rythme de versions |
| **Pipeline de middlewares** | Portes de skills déclenchées par mots-clés larges qui injectent des nudges d'activation sur les conversations « en forme mais inactives » | **Sorties rapides pour skills inactifs** : les portes de skills (deep-research, system-design, startup-sketch, etc.) ne se déclenchent que lorsque le skill est explicitement activé par slash ou chargé dans `skill_context`. Les requêtes anodines passent sans modification — pas de pollution du prompt, latence au premier token réduite |
| **Correction post-réponse** | Metacognition et portes similaires peuvent déclencher une seconde génération LLM complète pour « corriger » une réponse | **Corrections consultatives** : les nudges post-réponse arrivent au tour naturel suivant au lieu de forcer une re-génération immédiate, éliminant le pic de latence du second aller-retour LLM |
| **Observabilité des sous-agents** | Les cartes de sous-agents repliées n'affichent que le statut | **Métadonnées runtime en direct** : les cartes repliées affichent le nom du modèle effectif et l'utilisation cumulative de tokens, mis à jour après chaque appel LLM de sous-agent et durables après rechargement |
| **Persistance de session** | Cookie de session uniquement | **Politique « rester connecté »** : cycle de vie unifié des cookies de session, gestion `remember_me` et stratégie Secure/Max-Age selon le déploiement (HTTPS, loopback, HTTP public) |
| **Backends mémoire** | DeerMem par défaut | DeerMem par défaut **plus un backend HTTP OpenViking** pour le rappel mémoire distant et inter-instances |
| **Autorisation** | Désactivée par défaut | **Autorisation pluggable + fournisseur RBAC intégré** avec politiques d'autorisation/refus d'outils et de routes par rôle |
| **Corrélation des traces** | Basique | Propagation X-Trace-ID plus traçage Langfuse/LangSmith/Monocle avec corrélation `metadata.deerflow_trace_id` |
| **Code** | — | Le package harness (`backend/packages/harness/deerflow/`) est maintenu ici, avec ses propres tests, invariants (pare-feu d'import harness/app) et documentation |

L'ADN partagé demeure : skills, sous-agents, sandboxes, mémoire, MCP et les ponts vers les canaux IM. L'objectif d'UniDeer est la **latence prévisible** (pas de tokens gaspillés, pas de re-générations surprises) et la **profondeur opérationnelle** (propriété, baux, concurrence au niveau base de données, observabilité).

## Vue d'ensemble de l'architecture

### Topologie des services

Un déploiement standard exécute quatre services coopérants, orchestrés à partir d'une seule commande ou d'une pile Docker Compose :

| Service | Port | Rôle |
| --- | --- | --- |
| **Nginx** | `2026` | Point d'entrée de proxy inverse unifié. Route `/api/langgraph/*` vers le runtime LangGraph embarqué du Gateway et proxie tout le reste vers le Frontend. |
| **Gateway API** | `8001` | API REST FastAPI plus le runtime LangGraph embarqué (`RunManager`, `run_agent()`, `StreamBridge`). Il n'y a pas de service LangGraph autonome — le runtime vit dans le processus Gateway. |
| **Frontend** | `3000` | Interface web Next.js 16 (React 19, TypeScript, Tailwind CSS 4, pnpm). |
| **Provisioner** | `8002` | Optionnel — démarré uniquement lorsque la sandbox est configurée en mode provisioner/Kubernetes. Gère le cycle de vie des pods/VM sandbox. |

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

### Le pare-feu de dépendances harness / app

Le backend est divisé en deux couches avec une règle de dépendance stricte appliquée par la CI :

- `app.*` (l'hôte FastAPI : routeurs gateway, ponts de canaux, planificateur) **peut** importer `deerflow.*`
- `packages/harness/deerflow/` (le package harness, importé comme `deerflow.*`) **ne doit jamais** importer `app.*`

Ceci est appliqué par `backend/tests/test_harness_boundary.py`, qui s'exécute en CI. Le harness reste publiable, indépendant de l'app et testable isolément. Un second invariant est appliqué par `make test-blocking-io` : zéro I/O synchrone fichier/DB/réseau sur la boucle d'événements asynchrone — le travail bloquant doit être déchargé via `asyncio.to_thread`.

### Une requête typique, de bout en bout

1. L'utilisateur tape un message dans le compositeur du Frontend (optionnellement transcrit par voix ou poli par IA).
2. `POST /api/threads/{id}/runs/stream` ouvre une requête de streaming SSE.
3. Le Gateway valide l'authentification (sessions cookie Better Auth, CSRF, RBAC), résout la configuration de l'agent et crée une exécution LangGraph.
4. `RunManager.run_agent()` charge `ThreadState` depuis le checkpointer, résout le modèle et construit la chaîne de middlewares.
5. Le nœud de l'agent principal s'exécute : le middleware mémoire injecte le contexte utilisateur, l'activation de skill charge `SKILL.md` si activé par slash, le prompt système est assemblé (objectif, skills, outils, mémoire) et le modèle est appelé avec les définitions d'outils.
6. Si le modèle appelle des outils, ils sont routés vers les gestionnaires intégrés / sandbox / communauté / MCP, les résultats sont assainis et la détection de boucles s'exécute.
7. Si l'outil `task` est appelé, l'exécuteur de sous-agents génère des sous-agents parallèles avec des contextes isolés et des ensembles d'outils limités ; chacun rapporte un `TaskResult` structuré ; le lead synthétise.
8. Après l'exécution : l'extraction mémoire enregistre de nouveaux faits, un titre est généré (premier tour), les changements de workspace sont calculés, l'objectif est évalué et des suggestions sont produites.
9. `StreamBridge` convertit les événements internes en événements SSE (`values`, `messages-tuple`, `custom`, `tasks`) que le Frontend rend en direct : markdown animé, cartes de sous-agents avec chronologies d'étapes et utilisation de tokens, diffs de changements de workspace, todos, statut d'objectif et suggestions de suivi.

## Fonctionnalités principales

### Skills et outils

Les skills sont des modules de capacité structurés — un fichier `SKILL.md` définissant un workflow, des bonnes pratiques et des références à des ressources de support. UniDeer est livré avec plus de 30 skills intégrés et vous permet d'ajouter les vôtres, de remplacer les intégrés ou de les combiner en workflows composés.

**Comment les skills fonctionnent :**

1. Chaque skill vit dans son propre répertoire sous `skills/public/` (commité) ou `skills/custom/` (gitignoré).
2. Le fichier `SKILL.md` est le point d'entrée — les instructions que l'agent suit lorsque le skill est actif.
3. Les skills se chargent **progressivement** — seulement quand la tâche en a besoin, gardant la fenêtre de contexte légère.
4. Les skills peuvent déclarer `allowed-tools` pour restreindre les outils utilisables par l'agent pendant qu'il est actif (cadrage comportemental au mieux-effort).
5. **Activation par slash** : `/skill-name` au début d'une requête active le skill pour ce tour.
6. **SkillScan** : un scanner de sécurité déterministe s'exécute sur les skills installés, signalant les problèmes à haute confiance (clés privées, motifs d'exécution shell).

**Portes d'activation.** Les portes de skills spécifiques à un domaine (deep-research, system-design, startup-sketch, etc.) ne se déclenchent que lorsque le skill est explicitement actif dans le thread — activé par slash via `/skill-name` ou capturé dans `skill_context` après un chargement `read_file`. Une requête conversationnelle qui contient simplement des mots évocateurs de skills (par exemple « pourquoi... », « explique... » ou « design... ») passe sans modification : aucun nudge d'activation caché n'est injecté, donc les tours anodins ne polluent pas le prompt ni ne ralentissent la latence au premier token.

**Skills intégrés, notamment :**

- Recherche et analyse : `deep-research`, `github-deep-research`, `data-analysis`, `academic-paper-review`, `systematic-literature-review`, `consulting-analysis`
- Génération de contenu : `report-generation`, `ppt-generation`, `image-generation`, `video-generation`, `music-generation`, `podcast-generation`, `newsletter-generation`
- Ingénierie : `frontend-design`, `web-design-guidelines`, `chart-visualization`, `code-documentation`, `system-design`, `bootstrap`
- Produit et exigences : `business-requirement`, `product-requirements`, `software-requirements`, `startup-sketch`
- Méta : `skill-creator`, `skill-reviewer`, `find-skills`, `surprise-me`, `vercel-deploy-claimable`, `claude-to-deerflow`

La politique `allowed-tools` d'un skill ne s'applique qu'après activation explicite du skill. Le simple fait d'activer, de promouvoir ou de lister un skill dans une liste d'autorisation `skills` d'un agent personnalisé ou d'un sous-agent ne réduit pas l'ensemble d'outils normal de cet agent. Une fois actif, la politique filtre à la fois les schémas d'outils visibles par le modèle et l'exécution des outils. C'est un cadrage comportemental au mieux-effort, pas une frontière de sécurité dure.

### Le pipeline de middlewares

Le graphe de l'agent principal (`make_lead_agent`) assemble un pipeline de plus de 35 étages de middlewares (60+ modules dans l'arborescence source) qui enveloppent chaque appel de modèle et chaque exécution d'outil. C'est le principal point d'extension du harness.

Étages sélectionnés, dans l'ordre approximatif :

| Middleware | Rôle |
| --- | --- |
| `InputSanitization` | Neutralise les balises système malveillantes dans l'entrée brute |
| `ToolOutputBudget` | Plafonne les sorties d'outils trop grandes pour éviter le débordement du contexte |
| `ToolResultSanitization` | Assainit les résultats HTML/web distants récupérés |
| `ThreadData` / `Uploads` | Monte les portées d'isolation du thread et injecte les métadonnées des fichiers téléversés |
| `Sandbox` | Acquiert le conteneur sandbox ou le contexte local |
| `DanglingToolCall` | Répare les appels d'outils non aboutis après reprise d'interruption |
| `LLMErrorHandling` | Normalise les erreurs du fournisseur en tours récupérables |
| `SandboxAudit` | Inspecte par AST les commandes bash pour les motifs dangereux |
| `ReadBeforeWrite` | Applique la porte d'estampille SHA cryptographique avant l'écriture de fichiers |
| `ToolProgress` | Machine à états détectant la stagnation des outils (ACTIVE à WARNED à BLOCKED) |
| `SkillActivation` / `SkillToolPolicy` | Lie le contexte `SKILL.md` et applique `allowed-tools` |
| `Metacognition` | Application « penser d'abord » pour les prompts complexes (pré-réponse ; post-réponse consultative) |
| `Planner` | Règle « pas de plan, pas de modification » pour les mutations multi-étapes |
| `EmojiGate` | Scanner Unicode gardant le code/la configuration générés sans emojis |
| `Summarization` / `TokenBudget` | Compaction du contexte aux hauts niveaux de tokens |
| `TodoList` / `Title` | Suivi des tâches en mode plan et titres automatiques après le premier tour |
| `Memory` | Injecte la mémoire à long terme avant les exécutions, extrait de nouveaux faits après |
| `LoopDetection` | Arrête fermement les boucles répétitives d'appels d'outils identiques |
| `TerminalResponse` | Réessaie les réponses d'assistant vides ; empêche les échecs silencieux |
| `Safety / ModelLengthFinishReason` | Gère les filtres de contenu du fournisseur et les limites de tokens |
| `Clarification` (dernier) | Intercepte `ask_clarification` et émet `Command(goto=END)` |

La même chaîne (moins les étages propres à l'agent principal) est appliquée aux sous-agents, donc une tâche déléguée est gouvernée par les mêmes invariants que le parent.

### Sous-agents

Les sous-agents sont une optimisation, pas la réponse par défaut à une requête complexe.

L'agent principal génère des sous-agents à la volée — chacun avec son propre contexte, outils et conditions de terminaison — lorsque la délégation apporte un bénéfice net clair en latence parallèle réelle, en capacité spécialisée ou en isolation de contexte. Il garde les portées interdépendantes et les effets secondaires qui se chevauchent hors de la répartition parallèle. Les sous-agents rapportent des résultats structurés ; le lead vérifie et synthétise.

**Modèle d'exécution.** L'exécuteur de sous-agents est un hybride pool de threads + asyncio : les variables de contexte sont propagées correctement depuis le parent, chaque sous-agent exécute sa propre boucle d'événements isolée et l'état du cycle de vie suit une machine à états stricte : `PENDING` vers `RUNNING` vers `COMPLETED` / `FAILED` / `CANCELLED` / `TIMED_OUT`. Les plafonds de garde-fous (`token_capped`, `turn_capped`, `loop_capped`) terminent une exécution plus tôt en préservant la sortie partielle, et le lead peut distinguer « terminé » de « plafonné ».

**Limites de concurrence.** `SubagentLimitMiddleware` plafonne les délégations concurrentes (défaut 3, configurable 1-4) et les délégations totales par exécution (défaut 6, maximum 50).

**Contrats structurés.** Les résultats de sous-agents voyagent dans `ToolMessage.additional_kwargs` comme un contrat épinglé : statut, raison d'arrêt, erreur, empreinte SHA-256 du résultat complet, nom du modèle effectif et utilisation cumulée de tokens. Les valeurs d'énumération sont partagées entre Python et TypeScript via `contracts/subagent_status_contract.json`, et un test de contrat les épingle l'une à l'autre pour que le frontend et le backend ne puissent jamais diverger.

**Métadonnées runtime en direct.** Les cartes de sous-agents repliées affichent le modèle effectif et, lorsque le fournisseur renvoie des métadonnées d'utilisation, un total de tokens cumulé qui se met à jour après chaque appel LLM de sous-agent et persiste après rechargement. Les sous-agents concurrents gardent des totaux indépendants clés par `task_id`. Les fournisseurs qui omettent l'utilisation affichent un état indisponible explicite, jamais un zéro fabriqué.

Une recherche en lecture seule indépendante peut s'exécuter en parallèle lorsque le gain de temps réel dépasse le coût de découverte et de synthèse dupliquées. Un refactor de dépôt avec fichiers partagés et retours de tests séquentiels reste avec l'agent principal. Lorsque `max_concurrent_subagents` est 1, le guidage de routage parallèle et multi-lots est désactivé ; la délégation reste disponible uniquement pour un bénéfice matériel de spécialisation ou d'isolation de contexte.

### Sandbox et système de fichiers

Chaque tâche obtient son propre environnement d'exécution avec une vue complète du système de fichiers — skills, workspace, uploads, outputs.

```
/mnt/user-data/
├── uploads/          # your files
├── workspace/        # agents' working directory
└── outputs/          # final deliverables
```

**Fournisseurs :**

| Fournisseur | Description |
| --- | --- |
| `E2BSandboxProvider` | Sandbox E2B distante avec isolation VM, pool chaud, burst et propriété Redis pour les déploiements multi-travailleurs |
| `AioSandboxProvider` | Isolation par conteneurs (Docker) |
| `LocalSandboxProvider` | Système de fichiers hôte avec répertoires par thread ; bash hôte désactivé par défaut |

**Caractéristiques clés :**

- Isolation de répertoire par thread avec politiques de sécurité des chemins et politiques de variables d'environnement
- Verrous d'opérations de fichiers pour sérialiser les lectures/écritures concurrentes sur le même chemin
- **Application de la lecture avant écriture** : `read_file` estampille un hachage SHA-256 du contenu actuel du fichier sur le message ; `write_file` / `str_replace` sur un fichier existant est bloqué de manière déterministe à moins que le hachage sur disque ne corresponde à l'estampille. Toute écriture invalide les lectures antérieures, forçant une relecture entre modifications consécutives.
- **Suivi des changements de workspace** : après chaque exécution, un résumé diff des fichiers modifiés dans `workspace` et `outputs` est enregistré et affiché comme badge « files changed » avec diffs texte dans l'interface. Les uploads sont exclus (ce sont des entrées utilisateur).
- Gestion des images : les images base64 sont supprimées des points de contrôle après consommation par le modèle de vision pour éviter la duplication de charge utile.
- Recherche dans les fichiers de la sandbox avec l'outil `grep` intégré.

### Ingénierie du contexte

- **Contexte de sous-agent isolé** — les sous-agents ne peuvent pas voir l'historique du parent ni des frères
- **Résumé** — les sous-tâches terminées sont compactées, les résultats intermédiaires déchargés vers le système de fichiers et le contexte compressé pour rester dans les limites de tokens
- **Récupération stricte des appels d'outils** — les appels d'outils pendants sont réparés avec des résultats d'espace réservé avant l'invocation suivante du modèle, empêchant les modèles de raisonnement stricts d'échouer sur un historique malformé
- **Achèvement visible des exécutions d'outils** — une réponse finale vide après outil est réessayée une fois, puis présentée comme une erreur visible au lieu d'un succès silencieux
- **Compaction manuelle** — `/compact` dans le compositeur résume l'ancien contexte tout en gardant le chat complet visible
- **Objectifs de session** — `/goal <condition>` attache une condition d'achèvement à portée de thread ; le runtime évalue la conversation par rapport à l'objectif après chaque exécution et injecte des continuations cachées (plafond de sécurité de 8) jusqu'à ce qu'il soit satisfait ou effacé

### Mémoire à long terme

Mémoire persistante inter-sessions du profil utilisateur, des préférences et des connaissances accumulées.

**Architecture de stockage :**

```
{deerflow_home}/memory/
├── users/{user_id}/
│   ├── memory.json              # user profile + history summaries (JSON)
│   └── agents/{agent_name}/
│       └── facts/
│           ├── ab/cdef123...md  # individual fact (Markdown, sharded by SHA-256)
│           └── ...
```

- Les faits sont des fichiers Markdown canoniques, fragmentés par les deux premiers caractères hexadécimaux de `SHA-256(fact_id)`
- Les écritures journalisées empêchent les pertes silencieuses de mises à jour ; un verrou utilisateur partagé et des révisions optimistes protègent l'accès concurrent
- La récupération utilise un adaptateur SQLite FTS5/BM25 limité par défaut, avec repli sur sous-chaîne locale ; l'index dérivé est reconstruisible et les index corrompus sont recréés automatiquement
- Les faits `memory.json` hérités migrent automatiquement à la première lecture

**Backends :**

- **DeerMem** (défaut) — backend fichier, conscient de la portée, avec une porte d'écriture d'extraction qui classe chaque fait proposé par portée, durabilité et autorité avant stockage. Seuls les faits durables et descriptifs au niveau utilisateur sont stockés ; les contraintes du thread courant et les permissions ponctuelles restent dans l'état de la conversation.
- **OpenViking** (optionnel) — se connecte à un serveur OpenViking indépendant via HTTP pour le rappel distant et inter-instances. Des niveaux d'eau de soumission bornés et des tentatives avec gigue empêchent les commits dupliqués lors des nouvelles tentatives.

L'injection mémoire est configurable par mode d'opération (`middleware` vs `tool`), et `memory.injection_enabled: false` désactive entièrement le bloc.

### MCP et fabrique de modèles

UniDeer prend en charge le **Model Context Protocol** pour connecter des serveurs d'outils externes via stdio ou HTTP, avec cache de schémas d'outils, middleware de routage MCP et annotations d'outils pour les outils issus du MCP.

La fabrique de modèles est indépendante du fournisseur :

- API OpenAI et compatibles OpenAI (`langchain_openai:ChatOpenAI`)
- vLLM (auto-hébergé, avec prise en charge de la réflexion via `chat_template_kwargs.enable_thinking`)
- OpenAI Codex CLI (classe `gpt-5.4`) et Anthropic Claude (OAuth ou clé API)
- Huawei MindIE, plus des fournisseurs patchés (DeepSeek, MiniMax, StepFun, MiMo) pour le raisonnement

La prise en charge de la réflexion/du raisonnement (`supports_thinking`, `supports_reasoning_effort`), les modèles de vision et l'API Responses (`output_version: responses/v1`) sont tous de première classe. Les identifiants sont chargés depuis les variables d'environnement via le chargeur d'identifiants.

### Catalogue d'outils

**Outils intégrés** — `task` (génère un sous-agent), `tool_search` (découvre des outils par description), `ask_clarification` (pause pour saisie utilisateur), `view_image`, `present_file`, `list_uploaded_files`, `review_skill_package`, `setup_agent` / `update_agent`, `invoke_acp_agent`.

**Outils communautaires** — `web_search`, `web_fetch`, `web_capture`, `image_search` (fournisseur configurable).

**Outils sandbox** — `bash`, `ls`, `read_file` (avec plages de lignes), `write_file`, `str_replace`.

**Outils navigateur** (option supplémentaire) — `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_get_text`, `browser_back`, `browser_screenshot`, `browser_close`. Propulsé par Playwright avec filtrage SSRF ; désactivé par défaut.

**Autorisation.** Avec `authorization.enabled`, un `AuthorizationProvider` pluggable filtre les outils refusés avant qu'ils n'atteignent le modèle ou le catalogue d'outils différés, puis vérifie à nouveau avant chaque exécution d'outil métier. Le fournisseur RBAC intégré prend en charge les politiques d'autorisation/refus `tools` et `routes` par rôle.

## Runtime et fiabilité

### Propriété des exécutions, baux et récupération

Chaque exécution a un propriétaire. Le gestionnaire d'exécutions attribue un identifiant de travailleur unique (`hostname:hex_uuid`), estampille chaque exécution d'un bail et persiste la propriété dans la table runs. Si le Gateway redémarre ou qu'un travailleur devient injoignable avant qu'une exécution n'atteigne un état final durable, l'exécution est récupérée comme orpheline avec une raison d'arrêt claire :

- `"Gateway restarted before this run reached a durable final state."`
- `"Run lease expired - owning worker is unreachable."`

La détection d'expiration des baux, la récupération des orphelins au démarrage et la propriété multi-travailleurs des exécutions sont prises en charge sur SQLite (local) et Postgres (déployé). Les conflits de verrou SQLite transitoires lors de la finalisation du statut sont réessayés avec un backoff borné, et les signaux de contrainte d'unicité natifs du pilote (Postgres `23505`, codes de contrainte SQLite) sont détectés sans dépendre de textes d'erreur dépendants de la locale.

### Points de contrôle

L'état du thread est pointé de contrôle après chaque étape pour que les exécutions puissent reprendre ou bifurquer. Le runtime inclut des correctifs de compatibilité pour les mécanismes de points de contrôle LangGraph amont (par exemple, un correctif pour `InMemorySaver` perdant les écritures sur les threads migrés full-to-delta), épinglés à la version LangGraph validée et se désactivant automatiquement si l'amont corrige le problème. Les modes de canaux de points de contrôle et les fréquences de snapshot sont configurables par déploiement.

### Invariants de concurrence au niveau base de données

La concurrence est gouvernée par la base de données, pas par des drapeaux en mémoire. Les index uniques partiels appliquent les invariants essentiels :

| Index | Invariant |
| --- | --- |
| `uq_runs_thread_active` | Au plus une exécution pending/running par thread (`WHERE status IN ('pending','running')`) |
| `uq_scheduled_task_run_active` | Au plus une exécution active par tâche planifiée (`WHERE status IN ('queued','running')`) |
| `uq_channel_connection_active_identity` | Transfert à propriétaire unique actif pour les identités IM externes (`WHERE status != 'revoked'`) |

Les migrations incluent des étapes préalables de déduplication pour que les index puissent être construits même sur des bases de données qui violent déjà l'invariant (bases de terrain, déploiements multi-travailleurs d'avant correctif). L'écrivain perdant dans une course se manifeste comme un conflit typé (par exemple, `ActiveScheduledRunConflict`), et les répartitions planifiées qui chevauchent une exécution active enregistrent une pierre tombale terminale `skipped` qui n'occupe jamais le créneau actif.

## Démarrage rapide

### Prérequis

- Python 3.12+ et `uv`
- Node.js 22+ et pnpm 10
- `nginx` (requis pour le point de terminaison local unifié `make dev`)
- Docker (optionnel, pour le déploiement conteneurisé)

Exécutez `make check` pour vérifier la chaîne d'outils.

### Configuration

```bash
git clone https://github.com/bytedance/deer-flow.git
cd deer-flow
```

> L'URL de clonage ci-dessus pointe vers le dépôt amont. Pour UniDeer, clonez plutôt depuis l'URL de fork que vous avez reçue.

1. Installez les dépendances : `make install` (d'abord le backend, puis le frontend, comme implémenté par la cible)
2. Lancez l'assistant de configuration :

```bash
make setup
```

L'assistant vous guide dans le choix d'un fournisseur LLM, d'une recherche web optionnelle et des préférences d'exécution/sécurité telles que le mode sandbox, l'accès bash et les outils d'écriture de fichiers. Il génère un `config.yaml` minimal et écrit vos clés dans `.env`. Environ 2 minutes.

Exécutez `make doctor` à tout moment pour vérifier votre configuration et obtenir des conseils de correction exploitables. Si vous ouvrez un problème GitHub à propos d'un problème de configuration locale ou d'exécution, exécutez `make support-bundle` — il écrit un résumé de problème expurgé, un brouillon de problème assisté par IA et un zip de preuves optionnel sous `.deer-flow/support-bundles/`.

**Fichiers de configuration :**

- `config.yaml` (gitignoré) — la configuration principale de l'application : modèles, sandbox, outils, canaux, planificateur, journalisation, traçage
- `extensions_config.json` (gitignoré) — serveurs MCP et définitions de skills
- `config.example.yaml` / `extensions_config.example.json` — modèles à copier

Utilisez `make config-upgrade` pour fusionner les nouveaux champs de `config.example.yaml` dans un `config.yaml` existant sans perdre les paramètres locaux.

**Modèles** configurés dans `config.yaml` sous `models:`. Chaque entrée nomme une classe de fournisseur, un identifiant de modèle et des identifiants via variables d'environnement :

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

**Variables d'environnement** (chemins et état d'exécution) :

- `UNI_DEER_PROJECT_ROOT` — racine de projet explicite
- `UNI_DEER_CONFIG_PATH` — pointe vers un fichier de configuration spécifique
- `UNI_DEER_HOME` — emplacement de l'état d'exécution (défaut `.deer-flow` sous la racine du projet)
- `UNI_DEER_SKILLS_PATH` — répertoire des skills (défaut `skills/` sous la racine du projet)

### Lancement de l'application

**Option 1 : Docker (recommandé)**

```bash
make docker-start
```

Démarrage conscient du mode depuis `config.yaml`, point de terminaison unifié sur `http://localhost:2026`. Autres cibles : `make docker-stop`, `make docker-logs`, `make docker-logs-gateway`, `make docker-logs-frontend`, `make docker-logs-redis`.

**Option 2 : Développement local**

```bash
make dev
```

Démarre trois services avec rechargement à chaud :

- Gateway API (FastAPI, port 8001, avec le runtime LangGraph embarqué)
- Frontend (Next.js, port 3000)
- Nginx (port 2026 — le point d'entrée unifié)

Arrêtez tout avec `make stop`. Les journaux sont dans `logs/gateway.log`, `logs/frontend.log` et `logs/nginx.log`. Sous Windows, exécutez le flux local depuis Git Bash (les `cmd.exe`/PowerShell natifs ne sont pas pris en charge pour les scripts de service bash).

**Commandes de développement backend** (depuis `backend/`) :

```bash
make dev                # FastAPI Gateway with reload (port 8001)
make test               # offline unit tests
make test-blocking-io   # strict blocking-IO runtime gate
make lint               # ruff check
make format             # ruff format
make migrate-rev MSG="" # autogenerate an Alembic migration
```

**Commandes de développement frontend** (depuis `frontend/`) :

```bash
pnpm dev                # Next.js Turbopack dev server (port 3000)
pnpm lint               # ESLint
pnpm typecheck          # TypeScript check
pnpm test               # unit tests
pnpm test:e2e           # Playwright E2E tests
```

### Modes de démarrage

`config.yaml` prend en charge le démarrage conscient du mode :

| Mode | Description |
| --- | --- |
| `flash` | Réponses rapides, raisonnement minimal |
| `standard` | Vitesse et profondeur équilibrées |
| `pro` | Mode planification avec raisonnement explicite |
| `ultra` | Orchestration complète des sous-agents |

## Avancé

### Fournisseurs de sandbox

**E2B** utilise `wait` comme politique de débordement par défaut : il attend `acquire_timeout`, puis fait échouer le tour de l'agent (UniDeer ne réessaie pas automatiquement ; les clients peuvent utiliser l'erreur structurée pour planifier une nouvelle tentative). `burst` avec `burst_limit` autorise des VM supplémentaires limitées ; `reject` peut retirer une VM chaude avant de renvoyer une erreur. Avec la propriété Redis, `replicas` est une limite dure à l'échelle du déploiement partagée entre travailleurs via un hash de capacité ; les travailleurs incohérents échouent fermés.

**Aio** exécute le shell dans des conteneurs Docker isolés, les montages de données de thread étant détectés depuis son backend (les conteneurs locaux utilisent les répertoires gateway montés ; les sandboxes distantes/provisioner reçoivent les téléversements par synchronisation explicite).

**Local** mappe les outils de fichiers sur des répertoires par thread sur l'hôte, mais le `bash` hôte est désactivé par défaut car ce n'est pas une frontière d'isolation sécurisée. Ne réactivez que pour des workflows locaux entièrement fiables. Les commandes bash hôte ont un délai d'attente temps réel.

### Canaux IM

UniDeer s'intègre aux plateformes de messagerie externes : **Feishu, Slack, Telegram, Discord, DingTalk, WeChat, WeCom et GitHub**. Tous les canaux partagent un chemin d'exécution commun à travers le cycle de vie des exécutions du Gateway :

- Chaque canal reçoit les messages utilisateur, les convertit en exécutions de thread et renvoie les réponses en streaming
- La gestion de session (id d'assistant, limites de récursion, mode réflexion) est configurable par canal
- Un bus de messages, des politiques d'exécution par canal et la liaison d'identité de connexion unifient les 8 ponts
- **Transfert à propriétaire unique actif** : une identité externe est clé par `(provider, external_account_id, workspace_id)` ; la dernière liaison réussie gagne, appliquée sans course par l'index unique partiel `uq_channel_connection_active_identity`
- Déduplication des rediffusions entrantes, préparation des pièces jointes dans la sandbox et livraison des artefacts (outputs uniquement — les autres chemins sont rejetés pour empêcher l'exfiltration)

### Autorisation et RBAC

Les déploiements avancés peuvent activer l'autorisation pluggable avec `authorization.enabled` dans `config.yaml`. Un `AuthorizationProvider` configuré filtre les outils refusés avant qu'ils n'atteignent le modèle ou le catalogue d'outils différés, puis le même fournisseur est vérifié à nouveau avant chaque exécution d'outil métier. Les permissions de routes `threads:*` et `runs:*` du Gateway dérivent du même fournisseur, tandis que les vérifications de propriétaire existantes et les portes de gestion réservées aux admins restent en vigueur. Le fournisseur RBAC intégré prend en charge les politiques d'autorisation/refus `tools` et `routes` par rôle et valide que `default_role` nomme un rôle configuré. Désactivé par défaut.

### Traçage et observabilité

- **Corrélation des traces de requêtes** : chaque réponse HTTP du Gateway inclut `X-Trace-Id` ; les journaux incluent `trace_id`
- **Langfuse** : les traces incluent `metadata.deerflow_trace_id` correspondant à `X-Trace-Id` ; définissez `UNI_DEER_ENV` (ou `ENVIRONMENT`) pour taguer les traces par environnement de déploiement
- **LangSmith et Monocle** : fournisseurs de traçage pluggables
- Les callbacks de traçage sont attachés à la racine de l'invocation du graphe afin que les spans ne soient pas dupliqués ; la base de code documente explicitement cet invariant

### Tâches planifiées

Configurez des exécutions d'agents récurrentes depuis l'interface web ou l'API Gateway. Un planificateur en arrière-plan répartit chaque tâche selon son calendrier cron, avec :

- Sémantique appliquée par la base « au plus une exécution active par tâche » (`uq_scheduled_task_run_active`)
- Pierre tombale `skipped` lorsqu'une répartition chevauche une exécution active (n'occupe jamais le créneau actif)
- Les déclencheurs manuels en course avec le poller convergent vers le même résultat que le chemin rapide (manuel : conflit 409 ; planifié : `skipped`)

### Provisioner (Kubernetes)

Le service Provisioner optionnel (port 8002) gère l'infrastructure sandbox pour les déploiements basés sur Kubernetes : alloue des pods/VM sandbox à la demande, maintient des pools chauds pour une acquisition rapide et gère le cycle de vie complet (création, vérification de santé, destruction). Il n'est démarré que lorsque la sandbox est configurée en mode provisioner/K8s ; les déploiements locaux et Docker Compose avec les fournisseurs E2B/Aio n'en ont pas besoin.

## Client Python embarqué

Interagissez avec une instance UniDeer par programmation — pas d'interface web requise :

```python
from deerflow.client import DeerFlowClient

client = DeerFlowClient(base_url="http://localhost:8001")

# Stream a turn
for event in client.stream("thread-id", "your prompt"):
    print(event)

# Create a thread
thread = client.create_thread(agent="lead_agent")
```

Le client prend en charge la création de threads, le streaming de messages (mêmes modes SSE que l'interface), la gestion mémoire, les téléversements de fichiers et la configuration d'agents. Exécutez `make test-live` dans `backend/` pour les tests API en direct.

## Terminal Workbench (TUI)

Une interface terminal pour interagir avec UniDeer sans l'interface web — nouveaux threads, réponses en streaming, objectifs et commandes de skills depuis le CLI. Lancez-la avec la commande CLI `deerflow` ; sur un non-TTY, elle dégénère en sortie sans tête `--print` / `--json` pour les scripts.

## Déploiement

### Développement local

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

Un chart Helm vit dans `deploy/helm/deer-flow/` pour les déploiements Kubernetes, le Provisioner gérant l'infrastructure sandbox.

## Sécurité

UniDeer donne aux agents un vrai pouvoir sur le système de fichiers et l'exécution par conception. Le déploiement doit être traité comme une infrastructure privilégiée :

- **Un déploiement inapproprié peut introduire des risques de sécurité.** L'administrateur du gateway équivaut effectivement à une exécution de code sur l'hôte.
- La sandbox locale désactive le bash hôte par défaut ; ne réactivez que pour des workflows locaux entièrement fiables.
- Gardez `headless: true` et `allow_private_addresses: false` pour le contrôle du navigateur en dehors du débogage de confiance. Attacher un Chrome existant avec `cdp_url` ne peut pas appliquer la garde SSRF et échoue fermé sauf si `allow_unguarded_cdp: true` reconnaît explicitement le risque.
- Traitez `config.yaml` et `extensions_config.json` comme des fichiers contrôlés par l'opérateur de confiance : les déclarations de middlewares, d'outils, de modèles, de sandbox, de garde-fous et de MCP sont de l'exécution de code.
- L'authentification utilise des cookies HttpOnly, une protection CSRF et un RBAC pluggable ; la politique « rester connecté » rétrograde vers des cookies de session sur HTTP public et n'utilise Secure + Max-Age que sur HTTPS ou loopback.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — topologie des services, les 8 couches, flux de données, carte du dépôt, glossaire
- [Guide de contexte](context.md) — architecture système et contexte d'agent pour les agents de codage
- [Plans et RFC](docs/plans/) — autorisation, traçage, mémoire et plus
- [Contribution](CONTRIBUTING.md) — environnement de développement et workflow
- [Installation](Install.md) — instructions de configuration d'agent en une ligne

## Contribution

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour la configuration de l'environnement de développement, l'ordre de commandes requis et les attentes de validation. Avant de soumettre des modifications :

- Backend : `cd backend && make lint && make test` (parité CI : `uv sync --group dev`, puis lint, puis test)
- Frontend (si touché) : `cd frontend && pnpm lint && pnpm typecheck` ; définissez `BETTER_AUTH_SECRET` pour les builds de production
- Ne cassez jamais le pare-feu d'import harness/app (`tests/test_harness_boundary.py`)
- Gardez la boucle d'événements asynchrone sans I/O bloquant (`make test-blocking-io`)
- Mettez à jour la documentation lors de la modification des fonctionnalités (`README.md`) ou de l'architecture/middlewares (`AGENTS.md`)

## Licence

UniDeer est distribué sous la **licence MIT** — voir [LICENSE](LICENSE). En tant que fork de DeerFlow (également MIT), le droit d'auteur et l'attribution d'origine pour les parties dérivées du projet amont restent à ByteDance et aux contributeurs de DeerFlow.
