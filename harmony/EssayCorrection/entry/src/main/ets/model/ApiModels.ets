export class UserOut {
  id: string = '';
  username: string = '';
  display_name: string = '';
  role: string = 'student';

  static demo(role: string): UserOut {
    const user = new UserOut();
    user.id = role === 'teacher' ? 'teacher-1' : 'student-1';
    user.username = role === 'teacher' ? 'teacher@example.com' : 'student@example.com';
    user.display_name = role === 'teacher' ? '教师演示账号' : '学生演示账号';
    user.role = role;
    return user;
  }
}

export class LoginResponse {
  token: string = '';
  user: UserOut = new UserOut();

  static demo(role: string): LoginResponse {
    const result = new LoginResponse();
    result.token = `demo-token-${role}`;
    result.user = UserOut.demo(role);
    return result;
  }
}

export class LoginPayload {
  username: string = '';
  password: string = '';

  static create(username: string, password: string): LoginPayload {
    const payload = new LoginPayload();
    payload.username = username;
    payload.password = password;
    return payload;
  }
}

export class WritingPromptCreatePayload {
  title: string = '';
  prompt: string = '';

  static create(title: string, prompt: string): WritingPromptCreatePayload {
    const payload = new WritingPromptCreatePayload();
    payload.title = title;
    payload.prompt = prompt;
    return payload;
  }
}

export class ClassCreatePayload {
  name: string = '';

  static create(name: string): ClassCreatePayload {
    const payload = new ClassCreatePayload();
    payload.name = name;
    return payload;
  }
}

export class ClassJoinPayload {
  invite_code: string = '';

  static create(inviteCode: string): ClassJoinPayload {
    const payload = new ClassJoinPayload();
    payload.invite_code = inviteCode;
    return payload;
  }
}

export class ClassOut {
  id: string = '';
  name: string = '';
  invite_code: string = '';
  teacher_id: string = '';
  created_at: string = '';
  updated_at: string = '';
  student_count: number = 0;

  static demo(): ClassOut {
    const item = new ClassOut();
    item.id = 'class-demo-1';
    item.name = '演示班级';
    item.invite_code = 'CLASS2026';
    item.teacher_id = 'teacher-1';
    item.created_at = '2026-07-06T00:00:00Z';
    item.updated_at = '2026-07-06T00:00:00Z';
    item.student_count = 1;
    return item;
  }
}

export class WritingPromptOut {
  id: string = '';
  title: string = '';
  prompt: string = '';
  created_by: string = '';
  created_at: string = '';
  updated_at: string = '';

  static create(id: string, title: string, prompt: string, createdBy: string, createdAt: string, updatedAt: string): WritingPromptOut {
    const item = new WritingPromptOut();
    item.id = id;
    item.title = title;
    item.prompt = prompt;
    item.created_by = createdBy;
    item.created_at = createdAt;
    item.updated_at = updatedAt;
    return item;
  }

  static demo(): WritingPromptOut {
    return WritingPromptOut.create(
      'prompt-growth-choice',
      '一次选择',
      '请以成长中的一次选择为题写一篇作文。',
      'teacher-1',
      '2026-07-06T00:00:00Z',
      '2026-07-06T00:00:00Z'
    );
  }

  static demoList(): WritingPromptOut[] {
    return [
      WritingPromptOut.demo(),
      WritingPromptOut.create(
        'prompt-family-responsibility',
        '亲情与责任',
        '请围绕亲情与责任写一篇记叙文。',
        'teacher-1',
        '2026-07-05T00:00:00Z',
        '2026-07-05T00:00:00Z'
      )
    ];
  }
}

export class EssayCreatePayload {
  prompt_id: string | undefined = undefined;
  title: string = '';
  prompt: string = '';
  content: string = '';

  static create(promptId: string, title: string, prompt: string, content: string): EssayCreatePayload {
    const payload = new EssayCreatePayload();
    payload.prompt_id = promptId.length > 0 ? promptId : undefined;
    payload.title = title;
    payload.prompt = prompt;
    payload.content = content;
    return payload;
  }
}

export class EssayOut {
  id: string = '';
  prompt_id: string | undefined = undefined;
  title: string = '';
  prompt: string = '';
  content: string = '';
  student_id: string = '';
  status: string = '';
  created_at: string = '';
  updated_at: string = '';

  static demo(): EssayOut {
    const essay = new EssayOut();
    essay.id = 'demo-essay-1';
    essay.prompt_id = 'prompt-growth-choice';
    essay.title = '一次选择';
    essay.prompt = '请以成长中的一次选择为题写一篇作文。';
    essay.content = '那天我做出一个重要的的选择。首先我很犹豫，后来我明白成长需要承担责任。';
    essay.student_id = 'student-1';
    essay.status = 'analyzed';
    essay.created_at = '2026-07-06T00:00:00Z';
    essay.updated_at = '2026-07-06T00:00:00Z';
    return essay;
  }
}

export class AnalysisJobOut {
  id: string = '';
  essay_id: string = '';
  status: string = 'queued';
  provider: string = 'local-nlp';
  model: string = 'uer/chinese_roberta_L-2_H-128';
  started_at: string = '';
  finished_at: string | undefined = undefined;
  latency_ms: number = 0;
  error: string | undefined = undefined;

  static demo(essayId: string): AnalysisJobOut {
    const job = new AnalysisJobOut();
    job.id = 'demo-job-1';
    job.essay_id = essayId;
    job.status = 'completed';
    job.provider = 'local-nlp';
    job.model = 'uer/chinese_roberta_L-2_H-128';
    job.started_at = '2026-07-06T00:00:00Z';
    job.finished_at = '2026-07-06T00:00:01Z';
    job.latency_ms = 18;
    job.error = undefined;
    return job;
  }
}

export class AnalysisJobCreatePayload {
  provider: string = 'openai-compatible';

  static create(provider: string): AnalysisJobCreatePayload {
    const payload = new AnalysisJobCreatePayload();
    payload.provider = provider;
    return payload;
  }
}

export class GrammarIssue {
  id: string = '';
  start: number = 0;
  end: number = 0;
  issue_type: string = '';
  severity: string = 'low';
  message: string = '';
  suggestion: string = '';

  static create(id: string, start: number, end: number, issueType: string, message: string, suggestion: string): GrammarIssue {
    const issue = new GrammarIssue();
    issue.id = id;
    issue.start = start;
    issue.end = end;
    issue.issue_type = issueType;
    issue.severity = 'medium';
    issue.message = message;
    issue.suggestion = suggestion;
    return issue;
  }
}

export class SemanticMetric {
  score: number = 0;
  summary: string = '';
  evidence: string[] = [];

  static create(score: number, summary: string, evidence: string[]): SemanticMetric {
    const metric = new SemanticMetric();
    metric.score = score;
    metric.summary = summary;
    metric.evidence = evidence;
    return metric;
  }
}

export class ScoreDimension {
  name: string = '';
  score: number = 0;
  max_score: number = 0;
  comment: string = '';

  static create(name: string, score: number, maxScore: number, comment: string): ScoreDimension {
    const dimension = new ScoreDimension();
    dimension.name = name;
    dimension.score = score;
    dimension.max_score = maxScore;
    dimension.comment = comment;
    return dimension;
  }
}

export class RewriteSuggestion {
  issue_id: string = '';
  original: string = '';
  rewrite: string = '';
  rationale: string = '';
  improvement: string = '';
  issue_text: string = '';
  category: string = '语言表达';
  scope: string = 'sentence';
  priority: string = 'medium';
  paragraph_index: number = 0;
  sentence_index: number = 0;
  start: number = -1;
  end: number = -1;

  static create(issueId: string, original: string, rewrite: string, rationale: string,
    improvement: string = '', issueText: string = '', paragraphIndex: number = 0,
    sentenceIndex: number = 0, start: number = -1, end: number = -1): RewriteSuggestion {
    const suggestion = new RewriteSuggestion();
    suggestion.issue_id = issueId;
    suggestion.original = original;
    suggestion.rewrite = rewrite;
    suggestion.rationale = rationale;
    suggestion.improvement = improvement;
    suggestion.issue_text = issueText;
    suggestion.category = '语言表达';
    suggestion.scope = 'sentence';
    suggestion.priority = 'medium';
    suggestion.paragraph_index = paragraphIndex;
    suggestion.sentence_index = sentenceIndex;
    suggestion.start = start;
    suggestion.end = end;
    return suggestion;
  }
}

export class MaterialSuggestion {
  theme: string = '';
  material: string = '';
  usage_tip: string = '';

  static create(theme: string, material: string, usageTip: string): MaterialSuggestion {
    const suggestion = new MaterialSuggestion();
    suggestion.theme = theme;
    suggestion.material = material;
    suggestion.usage_tip = usageTip;
    return suggestion;
  }
}

export class ExampleOut {
  id: string = '';
  title: string = '';
  prompt: string = '';
  content: string = '';
  theme: string = '';
  highlights: string[] = [];

  static create(id: string, title: string, prompt: string, content: string, theme: string, highlights: string[]): ExampleOut {
    const item = new ExampleOut();
    item.id = id;
    item.title = title;
    item.prompt = prompt;
    item.content = content;
    item.theme = theme;
    item.highlights = highlights;
    return item;
  }

  static demoList(): ExampleOut[] {
    return [
      ExampleOut.create(
        'example-1',
        '把光留在心里',
        '请以成长中的一次选择为题写一篇作文。',
        '成长并不是每次都站到聚光灯下，而是在能够成全别人时，仍然感到心里有光。',
        '成长',
        ['细节具体', '立意清楚', '结尾点题']
      ),
      ExampleOut.create(
        'example-2',
        '旧伞下的新路',
        '请围绕亲情与责任写一篇记叙文。',
        '责任不是一句响亮的话，而是愿意在细小处替爱你的人多想一步。',
        '亲情',
        ['动作描写自然', '情感递进', '主题集中']
      )
    ];
  }
}

export class ProviderMeta {
  provider: string = 'local-nlp';
  model: string = 'uer/chinese_roberta_L-2_H-128';
  version: string = 'nltk-bert';
  latency_ms: number = 0;
  fallback_used: boolean = false;
  errors: string[] = [];

  static demo(): ProviderMeta {
    const meta = new ProviderMeta();
    meta.provider = 'local-nlp';
    meta.model = 'uer/chinese_roberta_L-2_H-128';
    meta.version = 'nltk-bert-2026-07-08';
    meta.latency_ms = 18;
    meta.fallback_used = true;
    meta.errors = ['后端不可用时显示本地演示结果'];
    return meta;
  }
}

export class AnalysisReport {
  essay_id: string = '';
  title: string = '';
  prompt: string = '';
  grammar_issues: GrammarIssue[] = [];
  coherence: SemanticMetric = new SemanticMetric();
  relevance: SemanticMetric = new SemanticMetric();
  total_score: number = 0;
  max_score: number = 100;
  dimensions: ScoreDimension[] = [];
  suggestions: RewriteSuggestion[] = [];
  materials: MaterialSuggestion[] = [];
  examples: ExampleOut[] = [];
  provider: ProviderMeta = new ProviderMeta();

  static demo(): AnalysisReport {
    const report = new AnalysisReport();
    report.essay_id = 'demo-essay-1';
    report.title = '一次选择';
    report.prompt = '请以成长中的一次选择为题写一篇作文。';
    report.grammar_issues = [
      GrammarIssue.create('grammar-duplicate-de', 9, 11, 'duplicate_particle', '疑似助词重复。', '删除一个“的”，或重写该短语。')
    ];
    report.coherence = SemanticMetric.create(82, '段落和句意衔接基本完整。', ['有明确事件推进', '结尾能够点题']);
    report.relevance = SemanticMetric.create(86, '内容与成长主题相关。', ['正文出现“成长”和“选择”等题目关键词']);
    report.total_score = 84;
    report.max_score = 100;
    report.dimensions = [
      ScoreDimension.create('内容充实', 25, 30, '素材明确，可继续补充细节。'),
      ScoreDimension.create('结构连贯', 21, 25, '起承转合基本清楚。'),
      ScoreDimension.create('主题相关', 22, 25, '扣题意识较强。'),
      ScoreDimension.create('语言表达', 16, 20, '个别表达可精炼。')
    ];
    report.suggestions = [];
    report.materials = [
      MaterialSuggestion.create('成长', '补充一个具体动作，如递出报名表、停顿、回头等。', '把心理变化放在动作后面写。')
    ];
    report.examples = ExampleOut.demoList();
    report.provider = ProviderMeta.demo();
    return report;
  }
}

export class ReportOverview {
  essay_id: string = '';
  prompt_id: string | undefined = undefined;
  prompt_title: string = '';
  title: string = '';
  submitted_at: string = '';
  status: string = '';
  total_score: number = 0;
  max_score: number = 100;
  provider: string = '';
  latency_ms: number = 0;
  teacher_review: TeacherReviewOut | undefined = undefined;

  static create(
    essayId: string,
    promptId: string,
    promptTitle: string,
    title: string,
    submittedAt: string,
    status: string,
    totalScore: number,
    maxScore: number,
    provider: string,
    latencyMs: number
  ): ReportOverview {
    const overview = new ReportOverview();
    overview.essay_id = essayId;
    overview.prompt_id = promptId.length > 0 ? promptId : undefined;
    overview.prompt_title = promptTitle;
    overview.title = title;
    overview.submitted_at = submittedAt;
    overview.status = status;
    overview.total_score = totalScore;
    overview.max_score = maxScore;
    overview.provider = provider;
    overview.latency_ms = latencyMs;
    return overview;
  }

  static fromEssayAndReport(essay: EssayOut, report: AnalysisReport): ReportOverview {
    return ReportOverview.create(
      report.essay_id,
      essay.prompt_id ?? '',
      essay.title,
      essay.title,
      essay.created_at,
      essay.status,
      report.total_score,
      report.max_score,
      report.provider.provider,
      report.provider.latency_ms
    );
  }

  static demoList(): ReportOverview[] {
    return [
      ReportOverview.create('demo-essay-1', 'prompt-growth-choice', '一次选择', '一次选择', '2026-07-06T00:00:00Z', 'analyzed', 84, 100, 'local-nlp', 18),
      ReportOverview.create('demo-essay-2', 'prompt-family-responsibility', '亲情与责任', '旧伞下的新路', '2026-07-05T00:00:00Z', 'analyzed', 87, 100, 'local-nlp', 16)
    ];
  }
}

export class ReportPromptGroup {
  prompt_id: string = '';
  prompt_title: string = '';
  reports: ReportOverview[] = [];

  static create(promptId: string, promptTitle: string, reports: ReportOverview[]): ReportPromptGroup {
    const group = new ReportPromptGroup();
    group.prompt_id = promptId;
    group.prompt_title = promptTitle;
    group.reports = reports;
    return group;
  }
}

export class TeacherReviewOut {
  id: string = '';
  essay_id: string = '';
  teacher_id: string = '';
  score: number = 0;
  comment: string = '';
  annotations: string[] = [];
  created_at: string = '';
  updated_at: string = '';

  static demo(essayId: string): TeacherReviewOut {
    const review = new TeacherReviewOut();
    review.id = 'demo-review-1';
    review.essay_id = essayId;
    review.teacher_id = 'teacher-1';
    review.score = 88;
    review.comment = '主题明确，建议补充更有画面感的细节。';
    review.annotations = ['第二段增加动作描写'];
    review.created_at = '2026-07-06T00:00:00Z';
    review.updated_at = '2026-07-06T00:00:00Z';
    return review;
  }
}

export class TeacherReviewPayload {
  score: number = 0;
  comment: string = '';
  annotations: string[] = [];

  static create(score: number, comment: string, annotations: string[]): TeacherReviewPayload {
    const payload = new TeacherReviewPayload();
    payload.score = score;
    payload.comment = comment;
    payload.annotations = annotations;
    return payload;
  }
}

export class TeacherEssayOut {
  essay: EssayOut = new EssayOut();
  latest_job: AnalysisJobOut | undefined = undefined;
  report_available: boolean = false;
  teacher_review: TeacherReviewOut | undefined = undefined;

  static demoList(): TeacherEssayOut[] {
    const item = new TeacherEssayOut();
    item.essay = EssayOut.demo();
    item.latest_job = AnalysisJobOut.demo(item.essay.id);
    item.report_available = true;
    item.teacher_review = undefined;
    return [item];
  }
}
