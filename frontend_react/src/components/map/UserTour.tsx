import React from 'react';
import { Joyride, STATUS } from 'react-joyride';

interface UserTourProps {
  run: boolean;
  onFinish: () => void;
  isCSGTOrAdmin?: boolean;
}

export const UserTour: React.FC<UserTourProps> = ({ run, onFinish, isCSGTOrAdmin }) => {
  const steps: any[] = [
    {
      target: '#map-container',
      title: '🗺️ Bản đồ giao thông trực quan',
      content: 'Đây là bản đồ giao thông trực quan của Đà Nẵng. Các tuyến đường sẽ tự động đổi màu xanh (thông thoáng), vàng (ùn ứ nhẹ) và đỏ (kẹt xe) dựa trên tốc độ di chuyển thực tế.',
      placement: 'center',
      disableBeacon: true,
    },
    {
      target: '#btn-filter-toggle',
      title: '🔍 Bộ lọc bản đồ',
      content: 'Click vào đây để mở bảng bộ lọc. Bạn có thể tra cứu theo tên đường, lọc theo Quận/Huyện, hoặc lọc theo mức độ kẹt xe trên bản đồ.',
      placement: 'right',
    },
    {
      target: '#btn-report-toggle',
      title: '🚨 Chế độ phản ánh kẹt xe',
      content: 'Bật chế độ phản ánh kẹt xe cộng đồng. Khi nút này sáng đỏ, bạn có thể click vào bất kỳ vị trí kẹt xe nào trên bản đồ để gửi phản ánh trực tiếp.',
      placement: 'right',
    },
    {
      target: '#btn-3d-toggle',
      title: '📦 Bản đồ 2D / 3D',
      content: 'Chuyển đổi giao diện bản đồ giữa chế độ 2D phẳng và chế độ 3D dựng khối các tòa nhà để dễ dàng quan sát địa hình.',
      placement: 'right',
    },
    {
      target: '#btn-report-current',
      title: '📍 Phản ánh nhanh tại vị trí hiện tại',
      content: 'Click để nhanh chóng gửi báo cáo kẹt xe tại vị trí định vị GPS hiện tại của bạn mà không cần định vị trên bản đồ.',
      placement: 'right',
    },
    {
      target: '#btn-snapshot-menu',
      title: '📸 Xuất/Nhập Snapshot bản đồ',
      content: 'Bấm vào đây để xuất ảnh chụp bản đồ (PNG) phục vụ báo cáo nhanh, hoặc xuất dữ liệu thô (CSV) và nhập lại snapshot bất kỳ lúc nào để khôi phục trạng thái bản đồ.',
      placement: 'right',
    },
    {
      target: '#btn-traffic-toggle',
      title: '👁️ Bật/Tắt đường giao thông',
      content: 'Bấm nút này để ẩn hoặc hiện toàn bộ các làn đường cảnh báo kẹt xe (xanh, vàng, đỏ) trên bản đồ khi bạn muốn xem bản đồ nền sạch hơn.',
      placement: 'right',
    },
    {
      target: '#btn-timeline-slider',
      title: '⏱️ Trục thời gian & Dự báo AI',
      content: 'Kéo thanh trượt để quay ngược thời gian xem lại lịch sử giao thông tối đa 6 tiếng trước, hoặc trượt về phía tương lai (+10p, +20p, +30p) để xem dự báo kẹt xe từ Trí tuệ Nhân tạo (AI).',
      placement: 'top',
    },
  ];

  // If logged in as CSGT or Admin, add administrative panel steps
  if (isCSGTOrAdmin) {
    steps.push(
      {
        target: '#nav-stats',
        title: '📊 Trang Thống kê',
        content: 'Xem báo cáo chi tiết về tình trạng giao thông đô thị, biểu đồ kẹt xe theo thời gian và xu hướng di chuyển trong ngày.',
        placement: 'bottom',
      },
      {
        target: '#nav-csgt',
        title: '👮 Bảng quản trị CSGT',
        content: 'Trang dành riêng cho Lực lượng CSGT để duyệt/từ chối các phản ánh kẹt xe cộng đồng, quản lý phân công điều phối giao thông trực tiếp.',
        placement: 'bottom',
      },
      {
        target: '#nav-incidents',
        title: '🚨 Quản lý Sự cố',
        content: 'Khai báo và theo dõi các sự cố giao thông (tai nạn, ngập lụt, lô cốt thi công) trên địa bàn thành phố để hệ thống tự động tìm tuyến đường tối ưu tránh điểm đen này.',
        placement: 'bottom',
      },
      {
        target: '#nav-scheduler',
        title: '📅 Lập lịch Scheduler & Crawler',
        content: 'Quản lý tiến trình cào dữ liệu giao thông tự động, theo dõi các chỉ số hiệu suất (KPIs) và đồ thị chạy scheduler trực quan.',
        placement: 'bottom',
      }
    );
  }

  steps.push({
    target: '#btn-help-tour',
    title: '❔ Hướng dẫn sử dụng',
    content: 'Bất cứ lúc nào cần hỗ trợ hoặc muốn xem lại hướng dẫn nhanh này, bạn chỉ cần bấm vào nút trợ giúp nổi trên bản đồ ở góc dưới này.',
    placement: 'right',
  });

  const handleJoyrideCallback = (data: any) => {
    const { status } = data;
    if (([STATUS.FINISHED, STATUS.SKIPPED] as string[]).includes(status)) {
      onFinish();
    }
  };

  const JoyrideComponent = Joyride as any;

  return (
    <JoyrideComponent
      key={run ? 'active' : 'inactive'}
      steps={steps}
      run={run}
      continuous={true}
      showProgress={true}
      showSkipButton={true}
      callback={handleJoyrideCallback}
      locale={{
        back: 'Quay lại',
        close: 'Đóng',
        last: 'Hoàn thành',
        next: 'Tiếp tục',
        open: 'Mở hướng dẫn',
        skip: 'Bỏ qua',
      }}
      styles={{
        options: {
          arrowColor: '#0f172a',
          backgroundColor: '#0f172a',
          overlayColor: 'rgba(2, 6, 23, 0.7)',
          primaryColor: '#3b82f6',
          textColor: '#e2e8f0',
          zIndex: 10000,
        },
        tooltip: {
          textAlign: 'left',
          borderRadius: '16px',
          backgroundColor: '#0f172a',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          padding: '16px',
        },
        tooltipTitle: {
          fontSize: '15px',
          fontWeight: 'bold',
          color: '#ffffff',
          marginBottom: '6px',
        },
        tooltipContent: {
          fontSize: '12.5px',
          color: '#cbd5e1',
          lineHeight: '1.6',
        },
        buttonNext: {
          fontSize: '11px',
          fontWeight: 'bold',
          borderRadius: '8px',
          backgroundColor: '#3b82f6',
          padding: '6px 12px',
        },
        buttonBack: {
          fontSize: '11px',
          fontWeight: 'semibold',
          color: '#94a3b8',
          marginRight: '12px',
        },
        buttonSkip: {
          fontSize: '11px',
          color: '#64748b',
          fontWeight: 'medium',
        }
      }}
    />
  );
};
