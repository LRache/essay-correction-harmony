import {
  AnalysisReport,
  ClassOut,
  EssayOut,
  ExampleOut,
  MaterialSuggestion,
  ReportPromptGroup,
  ReportOverview,
  RewriteSuggestion,
  ScoreDimension,
  TeacherEssayOut,
  TeacherReviewOut,
  UserOut,
  WritingPromptOut
} from '../model/ApiModels';
import { ApiClient } from '../service/ApiClient';

@Entry
@Component
struct Index {
  private tabsController: TabsController = new TabsController();
  private teacherTabsController: TabsController = new TabsController();
  private skipNextReportRefresh: boolean = false;
  @State currentTab: number = 0;
  @State teacherTab: number = 0;
  @State user: UserOut = UserOut.demo('student');
  @State isLoggedIn: boolean = false;
  @State loginRole: string = 'student';
  @State username: string = 'student@example.com';
  @State password: string = 'student123';
  @State statusText: string = '请先登录';
  @State isAnalyzing: boolean = false;
  @State selectedProviderIndex: number = 0;
  @State selectedProvider: string = 'local-nlp';
  @State titleText: string = '';
  @State promptText: string = '';
  @State essayText: string = '';
  @State essay: EssayOut = new EssayOut();
  @State report: AnalysisReport = AnalysisReport.demo();
  @State reportOverviews: ReportOverview[] = [];
  @State reportGroups: ReportPromptGroup[] = [];
  @State isReportDetailVisible: boolean = false;
  @State examples: ExampleOut[] = [];
  @State writingPrompts: WritingPromptOut[] = [];
  @State selectedPrompt: WritingPromptOut = new WritingPromptOut();
  @State isStudentWritingVisible: boolean = false;
  @State classList: ClassOut[] = [];
  @State classInviteCode: string = '';
  @State teacherClassNameText: string = '九年级一班';
  @State teacherEssays: TeacherEssayOut[] = [];
  @State selectedTeacherEssay: TeacherEssayOut = new TeacherEssayOut();
  @State isTeacherReviewVisible: boolean = false;
  @State teacherMachineReport: AnalysisReport = new AnalysisReport();
  @State isTeacherMachineReportVisible: boolean = false;
  @State isTeacherMachineReportLoading: boolean = false;
  @State teacherPromptTitleText: string = '校园里的温暖';
  @State teacherPromptText: string = '请围绕校园生活中的温暖瞬间写一篇记叙文。';
  @State reviewScore: string = '88';
  @State reviewComment: string = '主题明确，建议补充更有画面感的细节。';

  build() {
    Column() {
      if (!this.isLoggedIn) {
        this.LoginScreen()
      } else {
        this.AuthenticatedApp()
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F6F8FB')
  }

  @Builder
  LoginScreen() {
    Column({ space: 18 }) {
      Column({ space: 8 }) {
        Text('作文批改')
          .fontSize(30)
          .fontWeight(FontWeight.Bold)
          .fontColor('#162033')
        Text('登录后进入学生提交、批改报告、范文参考和教师管理')
          .fontSize(14)
          .fontColor('#5B6472')
          .textAlign(TextAlign.Center)
      }
      .width('100%')
      .alignItems(HorizontalAlign.Center)
      .margin({ top: 48 })

      this.LoginPanel()
    }
    .width('100%')
    .height('100%')
    .padding({ left: 18, right: 18 })
    .backgroundColor('#F6F8FB')
  }

  @Builder
  AuthenticatedApp() {
    Column() {
      this.Header()
      if (this.user.role === 'teacher') {
        this.TeacherWorkspace()
      } else {
        this.StudentWorkspace()
      }
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  StudentWorkspace() {
    Column() {
      Tabs({ barPosition: BarPosition.End, index: this.currentTab, controller: this.tabsController }) {
        TabContent() {
          this.StudentPanel()
        }.tabBar('提交')

        TabContent() {
          this.ReportPanel()
        }.tabBar('报告')

        TabContent() {
          this.ExamplesPanel()
        }.tabBar('范文')

        TabContent() {
          this.StudentClassPanel()
        }.tabBar('班级')

      }
      .onChange((index: number) => {
        this.currentTab = index;
        if (index === 1) {
          this.isReportDetailVisible = false;
          if (this.skipNextReportRefresh) {
            this.skipNextReportRefresh = false;
          } else {
            this.loadReportOverviews();
          }
        }
        if (index === 2) {
          this.loadExamples();
        }
        if (index === 3) {
          this.loadClasses();
        }
      })
      .width('100%')
      .height('100%')
    }
    .width('100%')
    .height('90%')
  }

  @Builder
  TeacherWorkspace() {
    Column() {
      Tabs({ barPosition: BarPosition.End, index: this.teacherTab, controller: this.teacherTabsController }) {
        TabContent() {
          this.TeacherClassPanel()
        }.tabBar('班级')

        TabContent() {
          this.TeacherPromptPanel()
        }.tabBar('出题')

        TabContent() {
          this.TeacherPanel()
        }.tabBar('批改')
      }
      .onChange((index: number) => {
        this.teacherTab = index;
        if (index === 0) {
          this.isTeacherReviewVisible = false;
          this.loadClasses();
        }
        if (index === 1) {
          this.isTeacherReviewVisible = false;
          this.loadWritingPrompts();
        }
        if (index === 2) {
          this.isTeacherReviewVisible = false;
          this.loadTeacherEssays();
        }
      })
      .width('100%')
      .height('100%')
    }
    .width('100%')
    .height('90%')
  }

  @Builder
  Header() {
    Row() {
      Column() {
        Text('作文批改')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
          .fontColor('#162033')
        Text(this.statusText)
          .fontSize(12)
          .fontColor('#5B6472')
          .maxLines(1)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
      }
      .alignItems(HorizontalAlign.Start)
      .width('62%')

      Column({ space: 4 }) {
        Text(this.isLoggedIn ? this.user.display_name : '未登录')
          .fontSize(13)
          .fontColor('#1E6B5C')
          .textAlign(TextAlign.End)
          .width('100%')
        if (this.isLoggedIn) {
          Button('登出')
            .width('100%')
            .height(28)
            .fontSize(12)
            .backgroundColor('#E2E8F0')
            .fontColor('#334155')
            .onClick(() => {
              this.logout();
            })
        }
      }
      .alignItems(HorizontalAlign.End)
      .width('38%')
    }
    .width('100%')
    .height('10%')
    .padding({ left: 18, right: 18, top: 10, bottom: 8 })
    .backgroundColor('#FFFFFF')
  }

  @Builder
  LoginPanel() {
    Scroll() {
      Column({ space: 14 }) {
        Row({ space: 8 }) {
          Button('学生')
            .width('48%')
            .backgroundColor(this.loginRole === 'student' ? '#1E6B5C' : '#DCE3EA')
            .fontColor(this.loginRole === 'student' ? '#FFFFFF' : '#1E293B')
            .onClick(() => {
              this.loginRole = 'student';
              this.username = 'student@example.com';
              this.password = 'student123';
            })
          Button('教师')
            .width('48%')
            .backgroundColor(this.loginRole === 'teacher' ? '#1E6B5C' : '#DCE3EA')
            .fontColor(this.loginRole === 'teacher' ? '#FFFFFF' : '#1E293B')
            .onClick(() => {
              this.loginRole = 'teacher';
              this.username = 'teacher@example.com';
              this.password = 'teacher123';
            })
        }
        .width('100%')

        TextInput({ placeholder: '账号', text: this.username })
          .onChange((value: string) => {
            this.username = value;
          })
          .width('100%')
        TextInput({ placeholder: '密码', text: this.password })
          .onChange((value: string) => {
            this.password = value;
          })
          .width('100%')

        Button('登录')
          .width('100%')
          .backgroundColor('#2563EB')
          .fontColor('#FFFFFF')
          .onClick(() => {
            this.login();
          })

        Text(this.statusText)
          .fontSize(12)
          .fontColor('#B45309')
          .textAlign(TextAlign.Center)
          .width('100%')

        this.SectionTitle('接口')
        Text('FastAPI: http://127.0.0.1:8000')
          .fontSize(14)
          .fontColor('#334155')
      }
      .width('100%')
      .padding(18)
    }
  }

  @Builder
  StudentPanel() {
    Column() {
      this.StudentWritingPanel()
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  StudentPromptListPanel() {
    Scroll() {
      Column({ space: 12 }) {
        this.SectionTitle('选择题目')
        if (this.writingPrompts.length === 0) {
          Text('暂无可作答题目')
            .fontSize(14)
            .fontColor('#64748B')
            .width('100%')
            .padding(14)
            .backgroundColor('#FFFFFF')
            .borderRadius(8)
        }
        ForEach(this.writingPrompts, (item: WritingPromptOut) => {
          this.WritingPromptSelectCard(item)
        }, (item: WritingPromptOut) => item.id)
      }
      .width('100%')
      .padding(18)
    }
  }

  @Builder
  StudentClassPanel() {
    Scroll() {
      Column({ space: 12 }) {
        this.SectionTitle('加入班级')
        TextInput({ placeholder: '请输入老师提供的邀请码', text: this.classInviteCode })
          .onChange((value: string) => {
            this.classInviteCode = value;
          })
          .width('100%')
        Button('加入班级')
          .width('100%')
          .backgroundColor('#1E6B5C')
          .fontColor('#FFFFFF')
          .onClick(() => {
            this.joinClass();
          })

        this.SectionTitle('我的班级')
        if (this.classList.length === 0) {
          Text('暂无已加入班级')
            .fontSize(14)
            .fontColor('#64748B')
            .width('100%')
            .padding(14)
            .backgroundColor('#FFFFFF')
            .borderRadius(8)
        }
        ForEach(this.classList, (item: ClassOut) => {
          this.ClassCard(item, false)
        }, (item: ClassOut) => item.id)
      }
      .width('100%')
      .padding(18)
    }
  }

  @Builder
  StudentWritingPanel() {
    Scroll() {
      Column({ space: 12 }) {
        Text('提交作文')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor('#162033')
          .width('100%')
          .textAlign(TextAlign.Start)

        this.SectionTitle('提交方式')
        this.CustomPromptCard()
        if (this.writingPrompts.length === 0) {
          Text('加入班级后可查看老师发布的题目')
            .fontSize(14)
            .fontColor('#64748B')
            .width('100%')
            .padding(14)
            .backgroundColor('#FFFFFF')
            .borderRadius(8)
        }
        ForEach(this.writingPrompts, (item: WritingPromptOut) => {
          this.WritingPromptSelectCard(item)
        }, (item: WritingPromptOut) => item.id)

        Text('作文要求')
          .fontSize(14)
          .fontWeight(FontWeight.Medium)
          .fontColor('#334155')
          .width('100%')
          .textAlign(TextAlign.Start)
        TextArea({ placeholder: '请输入作文题目、写作主题或具体要求', text: this.promptText })
          .onChange((value: string) => {
            this.promptText = value;
          })
          .width('100%')
          .height(100)
          .backgroundColor('#FFFFFF')

        Text('作文正文')
          .fontSize(14)
          .fontWeight(FontWeight.Medium)
          .fontColor('#334155')
          .width('100%')
          .textAlign(TextAlign.Start)
        TextArea({ placeholder: '请输入需要批改的作文正文', text: this.essayText })
          .onChange((value: string) => {
            this.essayText = value;
          })
          .width('100%')
          .height(260)
          .backgroundColor('#FFFFFF')

        Row({ space: 8 }) {
          Select([
            { value: 'BERT 模型' },
            { value: 'Moonshot 模型' }
          ])
            .selected(this.selectedProviderIndex)
            .value(this.selectedProviderIndex === 0 ? 'BERT 模型' : 'Moonshot 模型')
            .width('38%')
            .enabled(!this.isAnalyzing)
            .onSelect((index: number) => {
              this.selectedProviderIndex = index;
              this.selectedProvider = index === 0 ? 'local-nlp' : 'openai-compatible';
            })
          Button(this.isAnalyzing ? '正在批改...' : '开始批改')
            .width('34%')
            .backgroundColor('#1E6B5C')
            .fontColor('#FFFFFF')
            .enabled(!this.isAnalyzing)
            .onClick(() => {
              this.submitAndAnalyze();
            })
          Button('看报告')
            .width('24%')
            .backgroundColor('#F59E0B')
            .fontColor('#111827')
            .onClick(() => {
              this.navigateToTab(1);
            })
        }
        .width('100%')

      }
      .width('100%')
      .padding(18)
    }
  }

  @Builder
  ReportPanel() {
    Column() {
      if (this.isReportDetailVisible) {
        this.ReportDetailPanel()
      } else {
        this.ReportOverviewPanel()
      }
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  ReportOverviewPanel() {
    Scroll() {
      Column({ space: 12 }) {
        this.SectionTitle('报告概览')
        if (this.reportGroups.length === 0) {
          Text('暂无批改报告')
            .fontSize(14)
            .fontColor('#64748B')
            .width('100%')
            .padding(14)
            .backgroundColor('#FFFFFF')
            .borderRadius(8)
        }
        ForEach(this.reportGroups, (group: ReportPromptGroup) => {
          this.ReportPromptGroupSection(group)
        }, (group: ReportPromptGroup) => `${group.prompt_id}-${group.reports.length}`)
      }
      .width('100%')
      .padding(18)
    }
  }

  @Builder
  ReportDetailPanel() {
    Scroll() {
      Column({ space: 12 }) {
        Row({ space: 10 }) {
          Button('<')
            .width(40)
            .height(32)
            .fontSize(18)
            .backgroundColor('#E2E8F0')
            .fontColor('#334155')
            .onClick(() => {
              this.isReportDetailVisible = false;
              this.loadReportOverviews();
            })
          Text('报告详情')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor('#162033')
        }
        .width('100%')
        .alignItems(VerticalAlign.Center)

        Row() {
          Text(`${this.report.total_score}/${this.report.max_score}`)
            .fontSize(32)
            .fontWeight(FontWeight.Bold)
            .fontColor('#1E6B5C')
            .width('40%')
          Column() {
            Text(this.report.title)
              .fontSize(18)
              .fontWeight(FontWeight.Bold)
              .fontColor('#162033')
            Text(`模型：${this.report.provider.provider} · ${this.report.provider.latency_ms}ms`)
              .fontSize(12)
              .fontColor('#5B6472')
            if (this.report.provider.fallback_used) {
              Text(this.report.provider.provider === 'openai-compatible' ?
                'Moonshot 调用失败，已自动使用本地 BERT 完成批改' :
                '本地模型部分能力不可用，已使用降级分析')
                .fontSize(12)
                .fontColor('#B45309')
            }
          }
          .alignItems(HorizontalAlign.Start)
          .width('60%')
        }
        .width('100%')
        .padding(14)
        .backgroundColor('#FFFFFF')
        .borderRadius(8)

        this.SectionTitle('维度评分')
        ForEach(this.report.dimensions, (dimension: ScoreDimension) => {
          this.DimensionRow(dimension)
        }, (dimension: ScoreDimension) => dimension.name)

        this.SectionTitle('改写建议')
        if (this.report.suggestions.length === 0) {
          Text('暂无可定位的完整改写建议。可以结合维度评分和素材建议继续润色。')
            .fontSize(13)
            .fontColor('#64748B')
            .width('100%')
            .padding(12)
            .backgroundColor('#FFFFFF')
            .borderRadius(8)
        } else {
          ForEach(this.report.suggestions, (suggestion: RewriteSuggestion) => {
            this.SuggestionRow(suggestion)
          }, (suggestion: RewriteSuggestion) => suggestion.issue_id)
        }

        this.SectionTitle('素材建议')
        ForEach(this.report.materials, (material: MaterialSuggestion) => {
          this.MaterialRow(material)
        }, (material: MaterialSuggestion) => material.theme)
      }
      .width('100%')
      .padding(18)
    }
  }

  @Builder
  ExamplesPanel() {
    Scroll() {
      Column({ space: 12 }) {
        this.SectionTitle('优秀作文范例')
        ForEach(this.examples, (example: ExampleOut) => {
          this.ExampleCard(example)
        }, (example: ExampleOut) => example.id)
      }
      .width('100%')
      .padding(18)
    }
  }

  @Builder
  TeacherPanel() {
    Column() {
      if (this.isTeacherReviewVisible) {
        this.TeacherReviewPanel()
      } else {
        this.TeacherListPanel()
      }
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  TeacherClassPanel() {
    Scroll() {
      Column({ space: 12 }) {
        this.SectionTitle('创建班级')
        TextInput({ placeholder: '班级名称', text: this.teacherClassNameText })
          .onChange((value: string) => {
            this.teacherClassNameText = value;
          })
          .width('100%')
        Button('创建班级')
          .width('100%')
          .backgroundColor('#1E6B5C')
          .fontColor('#FFFFFF')
          .onClick(() => {
            this.createClass();
          })

        this.SectionTitle('我的班级')
        if (this.classList.length === 0) {
          Text('暂无班级')
            .fontSize(14)
            .fontColor('#64748B')
            .width('100%')
            .padding(14)
            .backgroundColor('#FFFFFF')
            .borderRadius(8)
        }
        ForEach(this.classList, (item: ClassOut) => {
          this.ClassCard(item, true)
        }, (item: ClassOut) => item.id)
      }
      .width('100%')
      .padding(18)
    }
  }

  @Builder
  TeacherPromptPanel() {
    Scroll() {
      Column({ space: 12 }) {
        this.SectionTitle('出题')
        TextInput({ placeholder: '题目标题', text: this.teacherPromptTitleText })
          .onChange((value: string) => {
            this.teacherPromptTitleText = value;
          })
          .width('100%')
        TextInput({ placeholder: '作文要求', text: this.teacherPromptText })
          .onChange((value: string) => {
            this.teacherPromptText = value;
          })
          .width('100%')
          .height(80)
        Button('发布题目')
          .width('100%')
          .backgroundColor('#1E6B5C')
          .fontColor('#FFFFFF')
          .onClick(() => {
            this.createTeacherPrompt();
          })

        this.SectionTitle('已发布题目')
        ForEach(this.writingPrompts, (item: WritingPromptOut) => {
          this.WritingPromptSummaryCard(item)
        }, (item: WritingPromptOut) => item.id)
      }
      .width('100%')
      .padding(18)
    }
  }

  @Builder
  TeacherListPanel() {
    Scroll() {
      Column({ space: 12 }) {
        this.SectionTitle('待批改作文')
        if (this.teacherEssays.length === 0) {
          Text('暂无待批改作文')
            .fontSize(14)
            .fontColor('#64748B')
            .width('100%')
            .padding(14)
            .backgroundColor('#FFFFFF')
            .borderRadius(8)
        }
        ForEach(this.teacherEssays, (item: TeacherEssayOut) => {
          this.TeacherEssayCard(item)
        }, (item: TeacherEssayOut) => item.essay.id)
      }
      .width('100%')
      .padding(18)
    }
  }

  @Builder
  TeacherReviewPanel() {
    Scroll() {
      Column({ space: 12 }) {
        Row({ space: 10 }) {
          Button('<')
            .width(40)
            .height(32)
            .fontSize(18)
            .backgroundColor('#E2E8F0')
            .fontColor('#334155')
            .onClick(() => {
              this.isTeacherReviewVisible = false;
              this.loadTeacherEssays();
            })
          Text('人工批改')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor('#162033')
        }
        .width('100%')
        .alignItems(VerticalAlign.Center)

        this.TeacherEssayDetailCard(this.selectedTeacherEssay)
        this.TeacherMachineReportPanel()
        this.SectionTitle('人工批改')
        TextInput({ placeholder: '分数', text: this.reviewScore })
          .onChange((value: string) => {
            this.reviewScore = value;
          })
          .width('100%')
        TextInput({ placeholder: '评语', text: this.reviewComment })
          .onChange((value: string) => {
            this.reviewComment = value;
          })
          .width('100%')
          .height(88)
        Button('提交人工批改')
          .width('100%')
          .backgroundColor('#2563EB')
          .fontColor('#FFFFFF')
          .onClick(() => {
            this.submitTeacherReview();
          })
      }
      .width('100%')
      .padding(18)
    }
  }

  @Builder
  TeacherMachineReportPanel() {
    Column({ space: 10 }) {
      this.SectionTitle('机器批改报告')
      if (this.isTeacherMachineReportLoading) {
        Text('正在加载机器批改报告...')
          .fontSize(14)
          .fontColor('#64748B')
          .width('100%')
          .padding(14)
          .backgroundColor('#FFFFFF')
          .borderRadius(8)
      } else if (!this.isTeacherMachineReportVisible) {
        Text('暂无机器批改报告，老师可先根据作文内容进行人工批改。')
          .fontSize(14)
          .fontColor('#64748B')
          .width('100%')
          .padding(14)
          .backgroundColor('#FFFFFF')
          .borderRadius(8)
      } else {
        Row() {
          Column() {
            Text('机器评分')
              .fontSize(13)
              .fontColor('#64748B')
            Text(`${this.teacherMachineReport.total_score}/${this.teacherMachineReport.max_score}`)
              .fontSize(28)
              .fontWeight(FontWeight.Bold)
              .fontColor('#1E6B5C')
          }
          .alignItems(HorizontalAlign.Start)
          .width('50%')
          Column() {
            Text('批改服务')
              .fontSize(13)
              .fontColor('#64748B')
              .textAlign(TextAlign.End)
              .width('100%')
            Text(this.teacherMachineReport.provider.provider)
              .fontSize(14)
              .fontColor('#334155')
              .textAlign(TextAlign.End)
              .width('100%')
          }
          .alignItems(HorizontalAlign.End)
          .width('50%')
        }
        .width('100%')
        .padding(14)
        .backgroundColor('#FFFFFF')
        .borderRadius(8)

        ForEach(this.teacherMachineReport.dimensions, (item: ScoreDimension) => {
          this.DimensionRow(item)
        }, (item: ScoreDimension) => item.name)

        this.SectionTitle('机器改写建议')
        if (this.teacherMachineReport.suggestions.length === 0) {
          Text('暂无可定位的完整改写建议。')
            .fontSize(13)
            .fontColor('#64748B')
            .width('100%')
            .padding(12)
            .backgroundColor('#FFFFFF')
            .borderRadius(8)
        } else {
          ForEach(this.teacherMachineReport.suggestions, (suggestion: RewriteSuggestion) => {
            this.SuggestionRow(suggestion)
          }, (suggestion: RewriteSuggestion) => suggestion.issue_id)
        }
      }
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
  }

  @Builder
  SectionTitle(text: string) {
    Text(text)
      .fontSize(16)
      .fontWeight(FontWeight.Bold)
      .fontColor('#162033')
      .width('100%')
      .margin({ top: 4 })
  }

  @Builder
  ClassCard(item: ClassOut, showInviteCode: boolean) {
    Column({ space: 8 }) {
      Row() {
        Text(item.name)
          .fontSize(17)
          .fontWeight(FontWeight.Bold)
          .fontColor('#162033')
          .width('60%')
        Text(`${item.student_count} 名学生`)
          .fontSize(12)
          .fontColor('#1E6B5C')
          .textAlign(TextAlign.End)
          .width('40%')
      }
      .width('100%')
      if (showInviteCode) {
        Text(`邀请码：${item.invite_code}`)
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor('#2563EB')
      }
      Text(`创建时间：${item.created_at}`)
        .fontSize(12)
        .fontColor('#64748B')
        .maxLines(1)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(8)
  }

  @Builder
  CustomPromptCard() {
    Column({ space: 6 }) {
      Row() {
        Text('自拟题目')
          .fontSize(16)
          .fontWeight(FontWeight.Bold)
          .fontColor('#162033')
          .width('70%')
        Text(this.selectedPrompt.id.length === 0 ? '已选择' : '选择')
          .fontSize(12)
          .fontColor('#2563EB')
          .textAlign(TextAlign.End)
          .width('30%')
      }
      .width('100%')
      Text('自行填写作文要求和正文，仅生成批改报告，不提交给老师。')
        .fontSize(13)
        .fontColor('#475569')
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(14)
    .backgroundColor(this.selectedPrompt.id.length === 0 ? '#ECFDF5' : '#FFFFFF')
    .borderRadius(8)
    .onClick(() => {
      this.useCustomPrompt();
    })
  }

  @Builder
  EssayCard(item: EssayOut) {
    Column({ space: 8 }) {
      Text(item.title)
        .fontSize(17)
        .fontWeight(FontWeight.Bold)
        .fontColor('#162033')
      Text(item.prompt)
        .fontSize(13)
        .fontColor('#475569')
      Text(item.content)
        .fontSize(14)
        .fontColor('#334155')
        .maxLines(4)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
      Text(`状态：${item.status}`)
        .fontSize(12)
        .fontColor('#1E6B5C')
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(8)
  }

  @Builder
  WritingPromptSelectCard(item: WritingPromptOut) {
    Column({ space: 6 }) {
      Row() {
        Text(item.title)
          .fontSize(16)
          .fontWeight(FontWeight.Bold)
          .fontColor('#162033')
          .width('70%')
        Text(this.selectedPrompt.id === item.id ? '已选择' : '选择')
          .fontSize(12)
          .fontColor('#2563EB')
          .textAlign(TextAlign.End)
          .width('30%')
      }
      .width('100%')
      Text(item.prompt)
        .fontSize(13)
        .fontColor('#475569')
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(14)
    .backgroundColor(this.selectedPrompt.id === item.id ? '#ECFDF5' : '#FFFFFF')
    .borderRadius(8)
    .onClick(() => {
      this.openStudentWriting(item);
    })
  }

  @Builder
  SelectedPromptCard(item: WritingPromptOut) {
    Column({ space: 8 }) {
      Text(item.title)
        .fontSize(18)
        .fontWeight(FontWeight.Bold)
        .fontColor('#162033')
      Text(item.prompt)
        .fontSize(13)
        .fontColor('#475569')
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(8)
  }

  @Builder
  WritingPromptSummaryCard(item: WritingPromptOut) {
    Column({ space: 6 }) {
      Text(item.title)
        .fontSize(15)
        .fontWeight(FontWeight.Bold)
        .fontColor('#162033')
      Text(item.prompt)
        .fontSize(13)
        .fontColor('#475569')
        .maxLines(2)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
      Text(`发布时间：${item.created_at}`)
        .fontSize(12)
        .fontColor('#64748B')
        .maxLines(1)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(12)
    .backgroundColor('#FFFFFF')
    .borderRadius(8)
  }

  @Builder
  ReportPromptGroupSection(group: ReportPromptGroup) {
    Column({ space: 8 }) {
      Text(group.prompt_title)
        .fontSize(16)
        .fontWeight(FontWeight.Bold)
        .fontColor('#162033')
      ForEach(group.reports, (item: ReportOverview) => {
        this.ReportOverviewCard(item)
      }, (item: ReportOverview) => item.essay_id)
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
  }

  @Builder
  ReportOverviewCard(item: ReportOverview) {
    Column({ space: 8 }) {
      Row() {
        Column() {
          Text(item.title)
            .fontSize(17)
            .fontWeight(FontWeight.Bold)
            .fontColor('#162033')
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
          Text(`提交时间：${item.submitted_at}`)
            .fontSize(12)
            .fontColor('#64748B')
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
        }
        .alignItems(HorizontalAlign.Start)
        .width('68%')

        Column() {
          Text(`${item.total_score}/${item.max_score}`)
            .fontSize(20)
            .fontWeight(FontWeight.Bold)
            .fontColor('#1E6B5C')
            .textAlign(TextAlign.End)
            .width('100%')
          Text(item.status)
            .fontSize(12)
            .fontColor('#5B6472')
            .textAlign(TextAlign.End)
            .width('100%')
        }
        .alignItems(HorizontalAlign.End)
        .width('32%')
      }
      .width('100%')

      Text(`批改服务：${item.provider} · ${item.latency_ms}ms`)
        .fontSize(12)
        .fontColor('#475569')
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(8)
    .onClick(() => {
      this.openReport(item);
    })
  }

  @Builder
  DimensionRow(item: ScoreDimension) {
    Column({ space: 6 }) {
      Row() {
        Text(item.name)
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor('#162033')
          .layoutWeight(1)
        Text(`${item.score}/${item.max_score}`)
          .fontSize(16)
          .fontWeight(FontWeight.Bold)
          .fontColor('#2563EB')
          .textAlign(TextAlign.End)
      }
      .width('100%')
      Text(item.comment)
        .fontSize(12)
        .fontColor('#64748B')
        .width('100%')
        .maxLines(4)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(12)
    .backgroundColor('#FFFFFF')
    .borderRadius(8)
  }

  @Builder
  SuggestionRow(item: RewriteSuggestion) {
    Column({ space: 6 }) {
      Row({ space: 8 }) {
        Text((item.category ?? '').length > 0 ? item.category : '语言表达')
          .fontSize(13)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1E6B5C')
          .layoutWeight(1)
        Text((item.priority ?? '').length > 0 ? item.priority : 'medium')
          .fontSize(12)
          .fontColor('#B45309')
      }
      .width('100%')
      Text(`修改位置：第 ${item.paragraph_index} 段，第 ${item.sentence_index} 句`)
        .fontSize(13)
        .fontWeight(FontWeight.Bold)
        .fontColor('#2563EB')
      if ((item.issue_text ?? '').length > 0) {
        Text(`问题片段：“${item.issue_text ?? ''}”`)
          .fontSize(12)
          .fontColor('#B45309')
      }
      if (this.hasRewriteExample(item)) {
        Text('修改后例句')
          .fontSize(12)
          .fontColor('#64748B')
        Text(item.rewrite ?? '')
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1E6B5C')
      } else {
        Text('修改建议')
          .fontSize(12)
          .fontColor('#64748B')
        Text(this.suggestionAdviceText(item))
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1E6B5C')
      }
      Text(`修改原因：${item.rationale ?? ''}`)
        .fontSize(12)
        .fontColor('#475569')
      Text(`这样修改的好处：${item.improvement ?? '修改后语句表达更准确，结构更清楚。'}`)
        .fontSize(12)
        .fontColor('#1E6B5C')
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(12)
    .backgroundColor('#FFFFFF')
    .borderRadius(8)
  }

  @Builder
  MaterialRow(item: MaterialSuggestion) {
    Column({ space: 6 }) {
      Text(item.theme)
        .fontSize(14)
        .fontWeight(FontWeight.Bold)
        .fontColor('#162033')
      Text(item.material)
        .fontSize(13)
        .fontColor('#334155')
      Text(item.usage_tip)
        .fontSize(12)
        .fontColor('#64748B')
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(12)
    .backgroundColor('#EEF6FF')
    .borderRadius(8)
  }

  @Builder
  ExampleCard(item: ExampleOut) {
    Column({ space: 8 }) {
      Row() {
        Text(item.title)
          .fontSize(17)
          .fontWeight(FontWeight.Bold)
          .fontColor('#162033')
          .width('70%')
        Text(item.theme)
          .fontSize(12)
          .fontColor('#1E6B5C')
          .textAlign(TextAlign.End)
          .width('30%')
      }
      Text(item.content)
        .fontSize(14)
        .fontColor('#334155')
      Text(item.highlights.join(' / '))
        .fontSize(12)
        .fontColor('#64748B')
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(8)
  }

  @Builder
  TeacherEssayCard(item: TeacherEssayOut) {
    Column({ space: 8 }) {
      Row() {
        Text(item.essay.title)
          .fontSize(17)
          .fontWeight(FontWeight.Bold)
          .fontColor('#162033')
          .maxLines(1)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
          .width('68%')
        Text(this.teacherReviewStatus(item))
          .fontSize(12)
          .fontColor(this.teacherReviewStatusColor(item))
          .textAlign(TextAlign.End)
          .width('32%')
      }
      .width('100%')
      Text(item.essay.content)
        .fontSize(14)
        .fontColor('#334155')
        .maxLines(3)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
      Text(item.report_available ? '已有机器批改报告' : '暂无机器批改报告')
        .fontSize(12)
        .fontColor(item.report_available ? '#1E6B5C' : '#B45309')
      Text('点击进入批改')
        .fontSize(12)
        .fontColor('#2563EB')
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(8)
    .onClick(() => {
      this.openTeacherReview(item);
    })
  }

  @Builder
  TeacherEssayDetailCard(item: TeacherEssayOut) {
    Column({ space: 8 }) {
      Text(item.essay.title)
        .fontSize(18)
        .fontWeight(FontWeight.Bold)
        .fontColor('#162033')
      Text(`作文要求：${item.essay.prompt}`)
        .fontSize(13)
        .fontColor('#475569')
      Text(item.essay.content)
        .fontSize(14)
        .fontColor('#334155')
      Row() {
        Text(item.report_available ? '已有机器批改报告' : '暂无机器批改报告')
          .fontSize(12)
          .fontColor(item.report_available ? '#1E6B5C' : '#B45309')
          .width('50%')
        Text(`作文状态：${item.essay.status}`)
          .fontSize(12)
          .fontColor('#64748B')
          .textAlign(TextAlign.End)
          .width('50%')
      }
      .width('100%')
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(8)
  }

  private async login(): Promise<void> {
    try {
      const result = await ApiClient.login(this.username, this.password);
      this.user = result.user;
      this.isLoggedIn = true;
      this.statusText = `${result.user.display_name} 已登录`;
      if (result.user.role === 'teacher') {
        this.currentTab = 0;
        this.teacherTab = 0;
        this.isTeacherReviewVisible = false;
        this.selectedTeacherEssay = new TeacherEssayOut();
        this.loadClasses();
        this.loadWritingPrompts();
        this.loadTeacherEssays();
      } else {
        this.currentTab = 0;
        this.isStudentWritingVisible = false;
        this.isReportDetailVisible = false;
        this.reportOverviews = [];
        this.reportGroups = [];
        this.loadClasses();
        this.loadWritingPrompts();
        this.loadReportOverviews();
        this.loadExamples();
      }
    } catch (e) {
      ApiClient.logout();
      this.isLoggedIn = false;
      this.handleRequestFailure();
    }
  }

  private logout(): void {
    ApiClient.logout();
    this.user = UserOut.demo('student');
    this.isLoggedIn = false;
    this.loginRole = 'student';
    this.username = 'student@example.com';
    this.password = 'student123';
    this.statusText = '已登出，请重新登录';
    this.currentTab = 0;
    this.teacherTab = 0;
    this.report = AnalysisReport.demo();
    this.reportOverviews = [];
    this.reportGroups = [];
    this.examples = [];
    this.isReportDetailVisible = false;
    this.writingPrompts = [];
    this.selectedPrompt = new WritingPromptOut();
    this.isStudentWritingVisible = false;
    this.classList = [];
    this.classInviteCode = '';
    this.teacherClassNameText = '九年级一班';
    this.teacherEssays = [];
    this.selectedTeacherEssay = new TeacherEssayOut();
    this.isTeacherReviewVisible = false;
    this.teacherMachineReport = new AnalysisReport();
    this.isTeacherMachineReportVisible = false;
    this.isTeacherMachineReportLoading = false;
  }

  private async submitAndAnalyze(): Promise<void> {
    await this.submitContentForAnalysis(this.promptText, this.essayText, this.selectedProvider);
  }

  private async submitContentForAnalysis(promptText: string, essayText: string, provider: string): Promise<void> {
    if (this.isAnalyzing) {
      this.statusText = '已有批改任务正在进行，请稍候';
      return;
    }
    const normalizedPrompt: string = promptText.trim();
    const normalizedEssay: string = essayText.trim();
    if (normalizedPrompt.length === 0) {
      this.statusText = '请输入作文要求';
      return;
    }
    if (normalizedEssay.length === 0) {
      this.statusText = '请输入需要批改的作文';
      return;
    }
    this.isAnalyzing = true;
    try {
      this.statusText = '正在提交作文...';
      const promptId: string = this.selectedPrompt.id.length > 0 ? this.selectedPrompt.id : '';
      const generatedTitle: string = this.selectedPrompt.title.length > 0 ? this.selectedPrompt.title :
        (normalizedPrompt.length > 18 ? `${normalizedPrompt.substring(0, 18)}…` : normalizedPrompt);
      const created: EssayOut = await ApiClient.submitEssay(promptId, generatedTitle, normalizedPrompt, normalizedEssay);
      this.essay = created;
      this.statusText = '正在生成批改报告...';
      await ApiClient.analyzeEssay(created.id, provider);
      this.report = await ApiClient.getReport(created.id);
      this.essay.status = 'analyzed';
      this.upsertReportOverview(this.report);
      this.isReportDetailVisible = false;
      this.skipNextReportRefresh = true;
      this.statusText = '批改完成，已加入报告概览';
      this.navigateToTab(1);
    } catch (e) {
      this.handleRequestFailure();
    } finally {
      this.isAnalyzing = false;
    }
  }

  private navigateToTab(index: number): void {
    this.currentTab = index;
    this.tabsController.changeIndex(index);
  }

  private async loadExamples(): Promise<void> {
    try {
      this.examples = await ApiClient.listExamples();
    } catch (e) {
      this.handleRequestFailure();
    }
  }

  private async loadWritingPrompts(): Promise<void> {
    try {
      const fetched: WritingPromptOut[] = await ApiClient.listWritingPrompts();
      this.writingPrompts = this.mergeWritingPrompts(fetched, this.writingPrompts);
    } catch (e) {
      this.handleRequestFailure();
    }
  }

  private async loadReportOverviews(): Promise<void> {
    if (!this.isLoggedIn || this.user.role !== 'student') {
      return;
    }
    try {
      const fetched: ReportOverview[] = await ApiClient.listReportOverviews();
      this.reportOverviews = this.mergeReportOverviews(this.reportOverviews, fetched);
      this.rebuildReportGroups();
    } catch (e) {
      this.handleRequestFailure();
    }
  }

  private async loadTeacherEssays(): Promise<void> {
    try {
      this.teacherEssays = await ApiClient.listTeacherEssays();
    } catch (e) {
      this.handleRequestFailure();
    }
  }

  private async loadClasses(): Promise<void> {
    try {
      this.classList = await ApiClient.listClasses();
    } catch (e) {
      this.handleRequestFailure();
    }
  }

  private async createClass(): Promise<void> {
    const name: string = this.teacherClassNameText.trim();
    if (name.length === 0) {
      this.statusText = '请填写班级名称';
      return;
    }
    try {
      const created: ClassOut = await ApiClient.createClass(name);
      this.classList = this.mergeClasses([created], this.classList);
      this.teacherClassNameText = '';
      this.statusText = `班级已创建，邀请码：${created.invite_code}`;
    } catch (e) {
      this.handleRequestFailure();
    }
  }

  private async joinClass(): Promise<void> {
    const inviteCode: string = this.classInviteCode.trim();
    if (inviteCode.length === 0) {
      this.statusText = '请输入班级邀请码';
      return;
    }
    try {
      const joined: ClassOut = await ApiClient.joinClass(inviteCode);
      this.classList = this.mergeClasses([joined], this.classList);
      this.classInviteCode = '';
      this.statusText = `已加入班级：${joined.name}`;
      this.loadWritingPrompts();
    } catch (e) {
      this.handleRequestFailure();
    }
  }

  private openStudentWriting(item: WritingPromptOut): void {
    this.selectWritingPrompt(item);
    this.isStudentWritingVisible = true;
    this.statusText = `正在作答：${item.title}`;
  }

  private async openTeacherReview(item: TeacherEssayOut): Promise<void> {
    this.selectedTeacherEssay = item;
    this.teacherMachineReport = new AnalysisReport();
    this.isTeacherMachineReportVisible = false;
    this.isTeacherMachineReportLoading = item.report_available;
    const review: TeacherReviewOut | undefined = item.teacher_review ?? undefined;
    if (review !== undefined) {
      this.reviewScore = `${review.score}`;
      this.reviewComment = review.comment;
    } else {
      this.reviewScore = '88';
      this.reviewComment = '';
    }
    this.isTeacherReviewVisible = true;
    this.statusText = `正在批改：${item.essay.title}`;
    if (item.report_available) {
      try {
        const loaded: AnalysisReport = await ApiClient.getReport(item.essay.id);
        this.teacherMachineReport = loaded;
        this.isTeacherMachineReportVisible = true;
        this.statusText = `正在批改：${item.essay.title}`;
      } catch (e) {
        this.isTeacherMachineReportVisible = false;
        this.statusText = '机器报告加载失败，可继续人工批改';
      } finally {
        this.isTeacherMachineReportLoading = false;
      }
    }
  }

  private async openReport(item: ReportOverview): Promise<void> {
    try {
      this.statusText = `正在打开报告：${item.title}`;
      const loaded: AnalysisReport = await ApiClient.getReport(item.essay_id);
      loaded.essay_id = item.essay_id;
      loaded.title = item.title;
      this.report = loaded;
      this.isReportDetailVisible = true;
      this.statusText = '报告已打开';
    } catch (e) {
      this.handleRequestFailure();
    }
  }

  private upsertReportOverview(report: AnalysisReport): void {
    const overview: ReportOverview = ReportOverview.fromEssayAndReport(this.essay, report);
    ApiClient.cacheReportOverview(overview);
    this.reportOverviews = this.mergeReportOverviews([overview], this.reportOverviews);
    this.rebuildReportGroups();
  }

  private mergeReportOverviews(primary: ReportOverview[], secondary: ReportOverview[]): ReportOverview[] {
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

  private mergeWritingPrompts(primary: WritingPromptOut[], secondary: WritingPromptOut[]): WritingPromptOut[] {
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

  private mergeClasses(primary: ClassOut[], secondary: ClassOut[]): ClassOut[] {
    const next: ClassOut[] = [];
    for (let index = 0; index < primary.length; index++) {
      next.push(primary[index]);
    }
    for (let index = 0; index < secondary.length; index++) {
      const item: ClassOut = secondary[index];
      let exists: boolean = false;
      for (let foundIndex = 0; foundIndex < next.length; foundIndex++) {
        const current: ClassOut = next[foundIndex];
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

  private hasRewriteExample(item: RewriteSuggestion): boolean {
    const rewrite: string = (item.rewrite ?? '').trim();
    const original: string = (item.original ?? '').trim();
    if (rewrite.length === 0 || rewrite === original) {
      return false;
    }
    if (rewrite.indexOf('可以') >= 0 || rewrite.indexOf('建议') >= 0 || rewrite.indexOf('例如') >= 0) {
      return false;
    }
    return (item.scope ?? '') === 'sentence' || rewrite.endsWith('。') || rewrite.endsWith('！') || rewrite.endsWith('？');
  }

  private suggestionAdviceText(item: RewriteSuggestion): string {
    const rewrite: string = (item.rewrite ?? '').trim();
    const original: string = (item.original ?? '').trim();
    if (this.hasRewriteExample(item) || original.length === 0) {
      return rewrite;
    }
    const originalWithoutEnd: string = this.trimSentenceEnd(original);
    let advice: string = rewrite;
    if (advice.indexOf(original) === 0) {
      advice = advice.substring(original.length).trim();
    } else if (originalWithoutEnd.length > 0 && advice.indexOf(originalWithoutEnd) === 0) {
      advice = advice.substring(originalWithoutEnd.length).trim();
    }
    advice = this.trimLeadingPunctuation(advice);
    return advice.length > 0 ? advice : rewrite;
  }

  private trimSentenceEnd(value: string): string {
    let next: string = value.trim();
    while (next.endsWith('。') || next.endsWith('！') || next.endsWith('？') ||
      next.endsWith('!') || next.endsWith('?')) {
      next = next.substring(0, next.length - 1).trim();
    }
    return next;
  }

  private trimLeadingPunctuation(value: string): string {
    let next: string = value.trim();
    while (next.startsWith('。') || next.startsWith('，') || next.startsWith('；') ||
      next.startsWith('：') || next.startsWith(',') || next.startsWith(';') ||
      next.startsWith(':')) {
      next = next.substring(1).trim();
    }
    return next;
  }

  private rebuildReportGroups(): void {
    const groups: ReportPromptGroup[] = [];
    for (let index = 0; index < this.reportOverviews.length; index++) {
      const item: ReportOverview = this.reportOverviews[index];
      const promptId: string = item.prompt_id ?? 'unassigned';
      const promptTitle: string = item.prompt_title.length > 0 ? item.prompt_title : item.title;
      let found: boolean = false;
      for (let groupIndex = 0; groupIndex < groups.length; groupIndex++) {
        const group: ReportPromptGroup = groups[groupIndex];
        if (group.prompt_id === promptId) {
          const nextReports: ReportOverview[] = [];
          for (let reportIndex = 0; reportIndex < group.reports.length; reportIndex++) {
            const reportItem: ReportOverview = group.reports[reportIndex];
            nextReports.push(reportItem);
          }
          nextReports.push(item);
          groups[groupIndex] = ReportPromptGroup.create(promptId, promptTitle, nextReports);
          found = true;
        }
      }
      if (!found) {
        const reports: ReportOverview[] = [item];
        groups.push(ReportPromptGroup.create(promptId, promptTitle, reports));
      }
    }
    this.reportGroups = groups;
  }

  private selectWritingPrompt(item: WritingPromptOut): void {
    this.selectedPrompt = item;
    this.titleText = item.title;
    this.promptText = item.prompt;
  }

  private useCustomPrompt(): void {
    this.selectedPrompt = new WritingPromptOut();
    this.titleText = '';
    this.promptText = '';
    this.statusText = '自拟题目只生成批改报告';
  }

  private async createTeacherPrompt(): Promise<void> {
    if (this.teacherPromptTitleText.length === 0 || this.teacherPromptText.length === 0) {
      this.statusText = '请填写题目标题和作文要求';
      return;
    }
    try {
      const created: WritingPromptOut = await ApiClient.createWritingPrompt(this.teacherPromptTitleText, this.teacherPromptText);
      const primary: WritingPromptOut[] = [created];
      this.writingPrompts = this.mergeWritingPrompts(primary, this.writingPrompts);
      this.teacherPromptTitleText = '';
      this.teacherPromptText = '';
      this.statusText = '题目已发布';
    } catch (e) {
      this.handleRequestFailure();
    }
  }

  private async submitTeacherReview(): Promise<void> {
    if (!this.isTeacherReviewVisible || this.selectedTeacherEssay.essay.id.length === 0) {
      this.statusText = '请先选择要批改的作文';
      return;
    }
    const score: number = Number(this.reviewScore);
    try {
      await ApiClient.reviewEssay(this.selectedTeacherEssay.essay.id, score, this.reviewComment);
      this.statusText = '人工批改已保存';
      this.teacherTab = 1;
      this.isTeacherReviewVisible = false;
      this.loadTeacherEssays();
    } catch (e) {
      this.handleRequestFailure();
    }
  }

  private handleRequestFailure(): void {
    this.statusText = '请求失败';
  }

  private teacherReviewStatus(item: TeacherEssayOut): string {
    const review: TeacherReviewOut | undefined = item.teacher_review ?? undefined;
    if (review !== undefined) {
      return '已人工批改';
    }
    return '待人工批改';
  }

  private teacherReviewStatusColor(item: TeacherEssayOut): string {
    const review: TeacherReviewOut | undefined = item.teacher_review ?? undefined;
    if (review !== undefined) {
      return '#1E6B5C';
    }
    return '#B45309';
  }
}
