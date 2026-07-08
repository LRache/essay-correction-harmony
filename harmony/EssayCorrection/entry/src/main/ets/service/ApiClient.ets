import http from '@ohos.net.http';
import {
  AnalysisJobOut,
  AnalysisJobCreatePayload,
  AnalysisReport,
  EssayCreatePayload,
  EssayOut,
  ExampleOut,
  LoginPayload,
  LoginResponse,
  ReportOverview,
  TeacherEssayOut,
  TeacherReviewOut,
  TeacherReviewPayload,
  WritingPromptCreatePayload,
  WritingPromptOut
} from '../model/ApiModels';

export class ApiClient {
  static baseUrl: string = 'http://10.249.42.57:8000';
  static authToken: string = '';
  static localWritingPrompts: WritingPromptOut[] = [];
  static localReportOverviews: ReportOverview[] = [];

  static logout(): void {
    ApiClient.authToken = '';
  }

  static async login(username: string, password: string): Promise<LoginResponse> {
    const payload: LoginPayload = LoginPayload.create(username, password);
    const raw: string = await ApiClient.request('/auth/login', http.RequestMethod.POST, payload, '');
    const parsed = JSON.parse(raw) as LoginResponse;
    ApiClient.authToken = parsed.token;
    return parsed;
  }

  static async submitEssay(promptId: string, title: string, prompt: string, content: string): Promise<EssayOut> {
    const payload: EssayCreatePayload = EssayCreatePayload.create(promptId, title, prompt, content);
    const raw: string = await ApiClient.request('/essays', http.RequestMethod.POST, payload, ApiClient.authToken);
    return JSON.parse(raw) as EssayOut;
  }

  static async listWritingPrompts(): Promise<WritingPromptOut[]> {
    const raw: string = await ApiClient.request('/writing-prompts', http.RequestMethod.GET, undefined, ApiClient.authToken);
    const fetched = JSON.parse(raw) as WritingPromptOut[];
    ApiClient.localWritingPrompts = ApiClient.mergeWritingPrompts(fetched, ApiClient.localWritingPrompts);
    return ApiClient.localWritingPrompts;
  }

  static async createWritingPrompt(title: string, prompt: string): Promise<WritingPromptOut> {
    const payload: WritingPromptCreatePayload = WritingPromptCreatePayload.create(title, prompt);
    const raw: string = await ApiClient.request('/teacher/prompts', http.RequestMethod.POST, payload, ApiClient.authToken);
    const created = JSON.parse(raw) as WritingPromptOut;
    ApiClient.cacheWritingPrompt(created);
    return created;
  }

  static cacheWritingPrompt(item: WritingPromptOut): void {
    const primary: WritingPromptOut[] = [item];
    ApiClient.localWritingPrompts = ApiClient.mergeWritingPrompts(primary, ApiClient.localWritingPrompts);
  }

  private static mergeWritingPrompts(primary: WritingPromptOut[], secondary: WritingPromptOut[]): WritingPromptOut[] {
    const next: WritingPromptOut[] = [];
    for (let index = 0; index < primary.length; index++) {
      const item: WritingPromptOut = primary[index];
      next.push(item);
    }
    for (let index = 0; index < secondary.length; index++) {
      const item: WritingPromptOut = secondary[index];
      let exists: boolean = false;
      for (let foundIndex = 0; foundIndex < next.length; foundIndex++) {
        const current: WritingPromptOut = next[foundIndex];
        if (current.id === item.id) {
          exists = true;
        }
      }
      if (!exists) {
        next.push(item);
      }
    }
    return next;
  }

  static async analyzeEssay(essayId: string, provider: string): Promise<AnalysisJobOut> {
    const payload: AnalysisJobCreatePayload = AnalysisJobCreatePayload.create(provider);
    const raw: string = await ApiClient.request(`/essays/${essayId}/analysis-jobs`, http.RequestMethod.POST, payload, ApiClient.authToken);
    return JSON.parse(raw) as AnalysisJobOut;
  }

  static async getReport(essayId: string): Promise<AnalysisReport> {
    const raw: string = await ApiClient.request(`/essays/${essayId}/report`, http.RequestMethod.GET, undefined, ApiClient.authToken);
    return JSON.parse(raw) as AnalysisReport;
  }

  static async listReportOverviews(): Promise<ReportOverview[]> {
    const raw: string = await ApiClient.request('/reports', http.RequestMethod.GET, undefined, ApiClient.authToken);
    const fetched = JSON.parse(raw) as ReportOverview[];
    ApiClient.localReportOverviews = ApiClient.mergeReportOverviews(fetched, ApiClient.localReportOverviews);
    return ApiClient.localReportOverviews;
  }

  static cacheReportOverview(item: ReportOverview): void {
    const primary: ReportOverview[] = [item];
    ApiClient.localReportOverviews = ApiClient.mergeReportOverviews(primary, ApiClient.localReportOverviews);
  }

  private static mergeReportOverviews(primary: ReportOverview[], secondary: ReportOverview[]): ReportOverview[] {
    const next: ReportOverview[] = [];
    for (let index = 0; index < primary.length; index++) {
      const item: ReportOverview = primary[index];
      next.push(item);
    }
    for (let index = 0; index < secondary.length; index++) {
      const item: ReportOverview = secondary[index];
      let exists: boolean = false;
      for (let foundIndex = 0; foundIndex < next.length; foundIndex++) {
        const current: ReportOverview = next[foundIndex];
        if (current.essay_id === item.essay_id) {
          exists = true;
        }
      }
      if (!exists) {
        next.push(item);
      }
    }
    return next;
  }

  static async listExamples(): Promise<ExampleOut[]> {
    const raw: string = await ApiClient.request('/examples', http.RequestMethod.GET, undefined, ApiClient.authToken);
    return JSON.parse(raw) as ExampleOut[];
  }

  static async listTeacherEssays(): Promise<TeacherEssayOut[]> {
    const raw: string = await ApiClient.request('/teacher/essays', http.RequestMethod.GET, undefined, ApiClient.authToken);
    return JSON.parse(raw) as TeacherEssayOut[];
  }

  static async reviewEssay(essayId: string, score: number, comment: string): Promise<TeacherReviewOut> {
    const annotations: string[] = ['教师端首版批注'];
    const payload: TeacherReviewPayload = TeacherReviewPayload.create(score, comment, annotations);
    const raw: string = await ApiClient.request(`/teacher/essays/${essayId}/review`, http.RequestMethod.POST, payload, ApiClient.authToken);
    return JSON.parse(raw) as TeacherReviewOut;
  }

  private static async request(path: string, method: http.RequestMethod, body: Object | undefined, token: string): Promise<string> {
    const client: http.HttpRequest = http.createHttp();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token.length > 0) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const options: http.HttpRequestOptions = {
      method: method,
      header: headers,
      expectDataType: http.HttpDataType.STRING,
      // Real LLM correction is synchronous on the backend and commonly takes
      // longer than a normal CRUD request.
      // Backend allows the external model up to 60 seconds. Keep the client
      // timeout slightly longer so it can receive either the result or the
      // backend's local-BERT fallback response.
      readTimeout: 90000,
      connectTimeout: 10000,
      usingCache: false
    };
    if (body !== undefined) {
      options.extraData = JSON.stringify(body);
    }
    try {
      const response: http.HttpResponse = await client.request(`${ApiClient.baseUrl}${path}`, options);
      client.destroy();
      if (response.responseCode < 200 || response.responseCode >= 300) {
        throw new Error(`HTTP ${response.responseCode}`);
      }
      return response.result as string;
    } catch (e) {
      client.destroy();
      throw new Error('请求失败');
    }
  }
}
