'use client';

import React, { createContext, useContext, useEffect, useState, useMemo, useCallback } from 'react';

export type Language = 'en' | 'vi';

export const DICTIONARY = {
  en: {
    // Navigation & Common
    app_name: 'Synthia',
    nav_dashboard: 'Dashboard',
    nav_monitor: 'Agent Monitor',
    nav_new_research: 'New Research',
    nav_main_menu: 'Main Menu',
    nav_recent: 'Recent Projects',
    nav_no_recent: 'No recent projects',
    nav_logout: 'Sign out',
    nav_settings: 'Settings',
    nav_language: 'Language',
    nav_all_monitors: 'All Monitors',
    nav_workspace: 'Workspace',

    // Settings Modal
    settings_title: 'System Settings',
    settings_desc: 'Customize platform preferences, language, and interface display.',
    settings_lang_label: 'Interface Language',
    settings_lang_desc: 'Select the primary display language across all dashboards and workspaces.',
    settings_lang_en: 'English (Default)',
    settings_lang_vi: 'Tiếng Việt (Vietnamese)',
    settings_default_badge: 'Default',
    settings_close: 'Close',
    settings_saved: 'Saved successfully',

    // Dashboard Header
    dash_badge: 'SYSTEM DASHBOARD',
    dash_subtitle: 'Scientific Research Platform',
    dash_title: 'Research Projects & Resource Usage',
    dash_desc: 'Overview of scientific research tasks, progress monitoring, and token/cost analytics.',
    dash_btn_refresh: 'Refresh',
    dash_btn_monitor: 'Agent Monitor',
    dash_btn_new: 'New Research',

    // Dashboard KPI Cards
    kpi_total_tasks: 'Total Projects',
    kpi_completion_rate: 'Completion Rate',
    kpi_in_progress: 'In Progress',
    kpi_needs_attention: 'Requires Attention',
    kpi_tokens_used: 'Tokens Consumed',
    kpi_avg_tokens: 'Avg per project',
    kpi_total_cost: 'Estimated Cost',
    kpi_avg_cost: 'Avg cost per project',

    // Method Analytics Table
    method_table_title: 'Resource Allocation by Methodology',
    method_table_badge: 'Analytics',
    method_table_desc: 'Comparison of token usage, estimated costs, and completion status across research methods.',
    method_table_collapse: 'Collapse table',
    method_table_expand: 'Expand table',
    method_col_method: 'Research Methodology',
    method_col_count: 'Projects (% of total)',
    method_col_tokens: 'Tokens Consumed',
    method_col_cost: 'Total Cost (USD)',
    method_col_avg: 'Avg Cost / Project',
    method_col_status: 'Completion Status',
    method_col_action: 'Filter',
    method_filter_active: 'Filtered',
    method_filter_btn: 'Filter method',

    method_review_name: 'Literature Review',
    method_review_badge: 'REVIEW',
    method_review_desc: 'Systematic review, synthesis of scientific sources and evidence.',
    method_comp_name: 'Computational Empirical',
    method_comp_badge: 'COMPUTATIONAL',
    method_comp_desc: 'Empirical data analysis, automated computational execution routines.',
    method_human_name: 'Fieldwork / Human Study',
    method_human_badge: 'FIELDWORK',
    method_human_desc: 'Methodology protocol design, awaiting empirical data collection.',

    // Task List & Filters
    tasks_list_title: 'Research Projects',
    tasks_list_desc: 'Track project status, human-in-the-loop checkpoints, and view generated reports.',
    search_placeholder: 'Search by title, question, or keyword...',
    filter_status_label: 'Status:',
    filter_all: 'All',
    filter_active: 'In Progress',
    filter_attention: 'Requires Attention',
    filter_completed: 'Completed',
    filter_type_label: 'Method:',
    filter_type_all: 'All Methods',
    filter_depth_label: 'Depth:',
    filter_depth_all: 'All Depths',
    filter_depth_shallow: 'Fast (SHALLOW)',
    filter_depth_standard: 'Standard (STANDARD)',
    filter_depth_deep: 'Comprehensive (DEEP)',
    reset_filters: 'Reset filters',

    // Table Headers
    th_title: 'Project Title & Question',
    th_method: 'Methodology & Citation',
    th_status: 'Status & Execution Step',
    th_cost: 'Cost & Token Usage',
    th_updated: 'Updated / Duration',
    th_actions: 'Actions',

    // Actions & Buttons
    btn_start: 'Start',
    btn_rerun: 'Rerun',
    btn_stop: 'Stop',
    btn_open_workspace: 'Workspace',
    btn_view_monitor: 'Monitor',
    btn_delete: 'Delete',

    // Task Confirmations & Prompts
    confirm_stop: 'Are you sure you want to stop this research task?',
    confirm_delete: 'Are you sure you want to permanently delete this research project and all associated files?',
    delete_error: 'Unable to delete research task.',
    start_error: 'Unable to start research task.',
    stop_error: 'Unable to cancel research task.',
    empty_filtered_title: 'No research projects match your current filters.',
    empty_workspace_title: 'No research projects in this workspace yet.',
    empty_workspace_desc: 'Click "New Research" to configure questions and let the research pipeline collect and analyze evidence.',
    btn_create_first: 'Create your first project',

    // Statuses
    status_pending: 'Pending',
    status_queued: 'Queued',
    status_running: 'In Progress',
    status_waiting_approval: 'Awaiting Plan Approval',
    status_waiting_user_data: 'Awaiting Data',
    status_completed: 'Completed',
    status_needs_review: 'Needs Review',
    status_partial: 'Partial Result',
    status_failed: 'Failed',
    status_cancelled: 'Cancelled',
    status_success: 'Finished',

    // Monitor Overview Page
    mon_page_badge: 'REAL-TIME MONITOR',
    mon_page_title: 'Research Execution Progress',
    mon_page_desc: 'Monitor autonomous execution steps, identify tasks needing plan approval or empirical data.',
    mon_card_running: 'Running / Queued',
    mon_card_running_sub: 'Active steps',
    mon_card_waiting: 'Awaiting Action',
    mon_card_waiting_sub: 'Plan review / Awaiting data',
    mon_card_attention: 'Needs Attention',
    mon_card_attention_sub: 'Errors or partial outputs',
    mon_card_completed: 'Completed',
    mon_card_completed_sub: 'Final reports available',
    mon_filter_inpage: 'Filter title on this page...',
    mon_table_header: 'Monitored Research Projects',
    mon_table_desc: 'Displays up to 20 projects per page. Idle or waiting tasks release workers to run other projects concurrently.',
    mon_open_detail: 'Open Monitor',
    mon_open_workspace: 'Open Workspace',
    mon_page_prev: 'Previous',
    mon_page_next: 'Next',
    mon_page_info: 'Page',

    // Monitor Detail Page
    mon_detail_run: 'Run',
    mon_detail_plan: 'Plan v',
    mon_detail_started: 'Started',
    mon_detail_sample: 'Sampled at',
    mon_detail_completed: 'Completed at',
    mon_lease_warning_title: 'Warning: Worker lease has expired',
    mon_lease_warning_desc: 'The processing worker did not refresh its lease in time. The system may reschedule this run; verify status before resuming.',
    mon_current_step: 'Latest Execution Step',
    mon_agent_assigned: 'Assigned Agent',
    mon_iteration: 'Iteration',
    mon_attempt: 'Worker attempt',
    mon_pipeline_title: 'Workflow Pipeline',
    mon_current_badge: 'Current',
    mon_backtrack_note: 'Non-linear Workflow: The research pipeline may backtrack from review stages to gather more evidence or revise drafts. Prior steps are not marked as permanently completed.',
    mon_counts_title: 'Saved Research Artifacts',
    mon_counts_desc: 'Cumulative results across iterations',
    mon_sources: 'Sources Gathered',
    mon_claims: 'Verified Claims',
    mon_reports: 'Report Versions',
    mon_artifacts: 'Artifacts & Charts',
    mon_experiments: 'Analysis Runs',
    mon_activity_log: 'Activity Log',
    mon_activity_sub: 'Newest first · Logs completed steps and summary metrics (not internal raw thoughts).',
    mon_no_activities: 'No activity records on this page yet.',
    mon_older: 'Older',
    mon_newer: 'Newer',
    mon_cost_ledger: 'Resource & Cost Ledger',
    mon_cost_est: 'Estimated cost incurred',
    mon_cost_source: 'Source',
    mon_cost_reserved: 'Reserved budget (unsettled)',
    mon_cost_tokens: 'Tokens recorded',
    mon_cost_disclaimer: 'Costs are calculated based on actual token usage with LLM providers; not an official invoice.',
    mon_milestones: 'System Milestones',
    mon_parallel_title: 'Concurrent Multitasking',
    mon_parallel_desc: 'You can safely run or switch between multiple research tasks. Waiting tasks release workers automatically.',

    // Common labels
    time_just_now: 'Just now',
    time_seconds: 'seconds',
    time_unknown: 'Unknown',
  },
  vi: {
    // Navigation & Common
    app_name: 'Synthia',
    nav_dashboard: 'Bảng điều khiển',
    nav_monitor: 'Giám sát Agent',
    nav_new_research: 'Nghiên cứu mới',
    nav_main_menu: 'Menu chính',
    nav_recent: 'Bài gần đây',
    nav_no_recent: 'Chưa có bài gần đây',
    nav_logout: 'Đăng xuất',
    nav_settings: 'Cài đặt',
    nav_language: 'Ngôn ngữ',
    nav_all_monitors: 'Tất cả bài giám sát',
    nav_workspace: 'Workspace',

    // Settings Modal
    settings_title: 'Cài đặt hệ thống',
    settings_desc: 'Tùy chỉnh ngôn ngữ hiển thị và cấu hình giao diện làm việc.',
    settings_lang_label: 'Ngôn ngữ giao diện',
    settings_lang_desc: 'Chọn ngôn ngữ hiển thị cho bảng điều khiển, tiến trình và không gian làm việc.',
    settings_lang_en: 'Tiếng Anh (English - Mặc định)',
    settings_lang_vi: 'Tiếng Việt (Vietnamese)',
    settings_default_badge: 'Mặc định',
    settings_close: 'Đóng',
    settings_saved: 'Đã lưu thay đổi',

    // Dashboard Header
    dash_badge: 'BẢNG ĐIỀU KHIỂN',
    dash_subtitle: 'Không gian nghiên cứu khoa học',
    dash_title: 'Tổng quan bài nghiên cứu & Chi phí tài nguyên',
    dash_desc: 'Quản lý các đề tài nghiên cứu khoa học, theo dõi tiến độ và kiểm tra chi phí tài nguyên.',
    dash_btn_refresh: 'Làm mới',
    dash_btn_monitor: 'Giám sát Agent',
    dash_btn_new: 'Nghiên cứu mới',

    // Dashboard KPI Cards
    kpi_total_tasks: 'Tổng số đề tài',
    kpi_completion_rate: 'Tỷ lệ hoàn thành',
    kpi_in_progress: 'Đang thực hiện',
    kpi_needs_attention: 'Cần chú ý',
    kpi_tokens_used: 'Tokens tiêu thụ',
    kpi_avg_tokens: 'Trung bình / đề tài',
    kpi_total_cost: 'Chi phí ước tính',
    kpi_avg_cost: 'Chi phí TB / đề tài',

    // Method Analytics Table
    method_table_title: 'Phân bổ tài nguyên theo phương pháp nghiên cứu',
    method_table_badge: 'Phân tích',
    method_table_desc: 'So sánh khối lượng token, chi phí ước tính ($USD) và tiến độ giữa các loại hình nghiên cứu.',
    method_table_collapse: 'Thu gọn bảng',
    method_table_expand: 'Mở rộng bảng',
    method_col_method: 'Phương pháp nghiên cứu',
    method_col_count: 'Số bài (% tổng)',
    method_col_tokens: 'Tokens tiêu thụ',
    method_col_cost: 'Tổng chi phí ($USD)',
    method_col_avg: 'Chi phí TB / bài',
    method_col_status: 'Tiến độ hoàn thành',
    method_col_action: 'Lọc',
    method_filter_active: 'Đang lọc',
    method_filter_btn: 'Lọc phương pháp',

    method_review_name: 'Tổng quan tài liệu',
    method_review_badge: 'REVIEW',
    method_review_desc: 'Tổng hợp tài liệu có hệ thống, đối chiếu nguồn bằng chứng khoa học.',
    method_comp_name: 'Thực nghiệm tính toán',
    method_comp_badge: 'COMPUTATIONAL',
    method_comp_desc: 'Phân tích dữ liệu thực nghiệm, chạy routine tính toán tự động.',
    method_human_name: 'Thực địa / Con người',
    method_human_badge: 'FIELDWORK',
    method_human_desc: 'Thiết kế đề cương phương pháp, chờ thu thập dữ liệu thực địa.',

    // Task List & Filters
    tasks_list_title: 'Danh sách bài nghiên cứu',
    tasks_list_desc: 'Theo dõi tiến trình, điểm dừng phê duyệt và mở bài báo đã hoàn thành.',
    search_placeholder: 'Tìm theo tiêu đề, câu hỏi nghiên cứu...',
    filter_status_label: 'Trạng thái:',
    filter_all: 'Tất cả',
    filter_active: 'Đang thực hiện',
    filter_attention: 'Cần chú ý',
    filter_completed: 'Đã hoàn thành',
    filter_type_label: 'Phương pháp:',
    filter_type_all: 'Tất cả phương pháp',
    filter_depth_label: 'Độ sâu:',
    filter_depth_all: 'Tất cả độ sâu',
    filter_depth_shallow: 'Nhanh (SHALLOW)',
    filter_depth_standard: 'Tiêu chuẩn (STANDARD)',
    filter_depth_deep: 'Chuyên sâu (DEEP)',
    reset_filters: 'Đặt lại bộ lọc',

    // Table Headers
    th_title: 'Tên đề tài & Câu hỏi nghiên cứu',
    th_method: 'Phương pháp & Kiểu trích dẫn',
    th_status: 'Trạng thái & Bước thực hiện',
    th_cost: 'Chi phí & Tokens',
    th_updated: 'Cập nhật / Thời lượng',
    th_actions: 'Thao tác',

    // Actions & Buttons
    btn_start: 'Bắt đầu',
    btn_rerun: 'Chạy lại',
    btn_stop: 'Dừng',
    btn_open_workspace: 'Workspace',
    btn_view_monitor: 'Giám sát',
    btn_delete: 'Xóa',

    // Task Confirmations & Prompts
    confirm_stop: 'Bạn có chắc muốn dừng bài nghiên cứu này?',
    confirm_delete: 'Bạn có chắc muốn xóa vĩnh viễn đề tài nghiên cứu này cùng toàn bộ dữ liệu liên quan?',
    delete_error: 'Không thể xóa đề tài nghiên cứu.',
    start_error: 'Không thể bắt đầu đề tài nghiên cứu.',
    stop_error: 'Không thể dừng đề tài nghiên cứu.',
    empty_filtered_title: 'Không tìm thấy bài nghiên cứu nào khớp với bộ lọc.',
    empty_workspace_title: 'Chưa có bài nghiên cứu nào trong không gian này.',
    empty_workspace_desc: 'Bấm nút "Nghiên cứu mới" để thiết lập mục tiêu và bắt đầu thu thập, phân tích tài liệu.',
    btn_create_first: 'Tạo bài nghiên cứu đầu tiên',

    // Statuses
    status_pending: 'Chưa bắt đầu',
    status_queued: 'Đang xếp hàng',
    status_running: 'Đang thực hiện',
    status_waiting_approval: 'Chờ duyệt kế hoạch',
    status_waiting_user_data: 'Chờ dữ liệu',
    status_completed: 'Đã hoàn thành',
    status_needs_review: 'Cần xem xét',
    status_partial: 'Kết quả một phần',
    status_failed: 'Gặp lỗi',
    status_cancelled: 'Đã hủy',
    status_success: 'Đã xong',

    // Monitor Overview Page
    mon_page_badge: 'GIÁM SÁT THỜI GIAN THỰC',
    mon_page_title: 'Theo dõi tiến trình các bài nghiên cứu',
    mon_page_desc: 'Quan sát các bước đang xử lý, phát hiện bài cần phê duyệt hoặc bổ sung dữ liệu.',
    mon_card_running: 'Đang chạy / Xếp hàng',
    mon_card_running_sub: 'Đang xử lý',
    mon_card_waiting: 'Đang chờ can thiệp',
    mon_card_waiting_sub: 'Duyệt kế hoạch / Chờ dữ liệu',
    mon_card_attention: 'Cần kiểm tra',
    mon_card_attention_sub: 'Có lỗi hoặc kết quả một phần',
    mon_card_completed: 'Đã hoàn thành',
    mon_card_completed_sub: 'Bản thảo hoàn tất',
    mon_filter_inpage: 'Lọc tiêu đề trong trang này...',
    mon_table_header: 'Danh sách bài nghiên cứu theo dõi',
    mon_table_desc: 'Mỗi trang hiển thị tối đa 20 bài. Bài đang chờ không chiếm giữ worker, bạn có thể chạy bài khác song song.',
    mon_open_detail: 'Mở giám sát',
    mon_open_workspace: 'Mở bài viết',
    mon_page_prev: 'Trang trước',
    mon_page_next: 'Trang sau',
    mon_page_info: 'Trang',

    // Monitor Detail Page
    mon_detail_run: 'Lần nghiên cứu',
    mon_detail_plan: 'Kế hoạch v',
    mon_detail_started: 'Khởi chạy',
    mon_detail_sample: 'Lấy mẫu',
    mon_detail_completed: 'Hoàn tất lúc',
    mon_lease_warning_title: 'Cảnh báo: Thời hạn nhận việc của Worker đã hết',
    mon_lease_warning_desc: 'Worker chưa làm mới lease. Hệ thống có thể cần phục hồi lần chạy; hãy kiểm tra trước khi tiếp tục.',
    mon_current_step: 'Bước xử lý gần nhất',
    mon_agent_assigned: 'Tác tử phụ trách',
    mon_iteration: 'Vòng lặp',
    mon_attempt: 'Lượt worker',
    mon_pipeline_title: 'Chuỗi chặng nghiên cứu',
    mon_current_badge: 'Hiện tại',
    mon_backtrack_note: 'Quy trình phi tuyến tính: Hệ thống có thể quay lui từ khâu phản biện để thu thập thêm nguồn hoặc chỉnh sửa. Các bước trước không đánh dấu hoàn thành vĩnh viễn.',
    mon_counts_title: 'Kết quả nghiên cứu đã lưu trữ',
    mon_counts_desc: 'Dữ liệu tích lũy qua các vòng lặp',
    mon_sources: 'Nguồn thu thập',
    mon_claims: 'Luận điểm có bằng chứng',
    mon_reports: 'Bản thảo bài báo',
    mon_artifacts: 'Tệp kết quả & Đồ thị',
    mon_experiments: 'Lần phân tích',
    mon_activity_log: 'Nhật ký hoạt động',
    mon_activity_sub: 'Mới nhất trước · Ghi nhận các bước hoàn tất và tóm tắt kết quả (không phải suy nghĩ nội bộ).',
    mon_no_activities: 'Chưa có bản ghi hoạt động nào ở trang này.',
    mon_older: 'Cũ hơn',
    mon_newer: 'Mới hơn',
    mon_cost_ledger: 'Tài nguyên & Chi phí ghi nhận',
    mon_cost_est: 'Chi phí ước tính đã phát sinh',
    mon_cost_source: 'Nguồn',
    mon_cost_reserved: 'Ngân sách đặt chỗ (chưa đối chiếu)',
    mon_cost_tokens: 'Token LLM đã ghi nhận',
    mon_cost_disclaimer: 'Chi phí dựa trên token thực tế với provider; không phải hóa đơn chính thức.',
    mon_milestones: 'Mốc thời gian hệ thống',
    mon_parallel_title: 'Làm việc song song',
    mon_parallel_desc: 'Bạn có thể mở hoặc chạy nhiều đề tài đồng thời. Bài chờ duyệt sẽ giải phóng worker tự động.',

    // Common labels
    time_just_now: 'Vừa xong',
    time_seconds: 'giây',
    time_unknown: 'Không rõ',
  },
};

export type TranslationKey = keyof typeof DICTIONARY.en;

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: TranslationKey) => string;
}

const LanguageContext = createContext<LanguageContextType>({
  language: 'en',
  setLanguage: () => {},
  t: (key) => DICTIONARY.en[key] || key,
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  // Default is 'en' as requested: "trong cài đặt có chuyển toàn bộ sang tiếng anh và mặc định là tiếng anh"
  const [language, setLanguageState] = useState<Language>('en');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem('synthia_lang') as Language | null;
      if (saved === 'en' || saved === 'vi') {
        setLanguageState(saved);
        if (typeof document !== 'undefined') {
          document.documentElement.lang = saved;
        }
      } else {
        // default explicitly to 'en'
        setLanguageState('en');
        localStorage.setItem('synthia_lang', 'en');
        if (typeof document !== 'undefined') {
          document.documentElement.lang = 'en';
        }
      }
    } catch {}
    setMounted(true);
  }, []);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    try {
      localStorage.setItem('synthia_lang', lang);
      if (typeof document !== 'undefined') {
        document.documentElement.lang = lang;
      }
    } catch {}
  }, []);

  const t = useCallback((key: TranslationKey): string => {
    const dict = DICTIONARY[language] || DICTIONARY.en;
    return dict[key] || DICTIONARY.en[key] || key;
  }, [language]);

  const value = useMemo(() => ({ language, setLanguage, t }), [language, setLanguage, t]);

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
