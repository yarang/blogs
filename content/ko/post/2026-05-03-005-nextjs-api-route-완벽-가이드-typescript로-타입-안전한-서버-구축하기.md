+++
title = "Next.js API Route 완벽 가이드: TypeScript로 타입 안전한 서버 구축하기"
date = 2026-05-03T12:48:53+09:00
draft = false
tags = ["Next.js", "TypeScript", "API", "Node.js", "Web Development"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# Next.js API Route 완벽 가이드: TypeScript로 타입 안전한 서버 구축하기

최근 **Hacker News**를 통해 Mercury의 Haskell 기반 백엔드 이야기가 화제가 되었습니다. 대규모 트래픽을 처리하는 견고한 시스템이 중요하지만, 우리 같은 일반적인 웹 개발자에게는 **빠른 개발 속도와 유지보수성**이 필수적입니다. 특히 스타트업이나 개인 프로젝트에서는 프레임워크의 편리함을 포기하기 어렵습니다.

이번 포스트에서는 **Next.js API Routes**를 사용하여 타입 안전성을 확보하면서도 효율적인 서버 사이드 로직을 구축하는 방법을 다뤄보겠습니다. 앞서 구축한 'AI 자동 댓글 시스템'이나 'MCP 서버'의 백엔드 처럼, API와 프론트엔드를 하나의 저장소에서 관리하는 모노리포(Monorepo) 스타일의 장점을 극대화하는 방법입니다.

## 1. API Routes vs Route Handlers (App Router)

Next.js를 사용할 때 가장 먼저 겪는 고민은 "Pages Router의 `pages/api`를 쓸 것인가, App Router의 `route.ts`를 쓸 것인가"입니다.

- **Pages Router (`pages/api`):** Node.js 서버 환경에 의존하며, 미들웨어 설정이 직관적입니다. 기존 Node.js 생태계의 미들웨어를 그대로 사용하기 좋습니다.
- **App Router (`app/api`):** Edge Runtime 지원으로 더 빠른 시작 시간과 전 세분산 배포가 가능하지만, Node.js 전용 기능(예: 파일 시스템 직접 접근) 사용에 제약이 있을 수 있습니다.

이 가이드에서는 현재 가장 안정적이고 직관적인 **Pages Router 기반의 API Routes**를 예제로 다루지만, 타입 입력 방식은 App Router에서도 동일하게 적용할 수 있습니다.

## 2. 문제점: Loose한 Request/Response 타입

Next.js API 핸들러의 기본 타입 정의는 다음과 같습니다.

```typescript
import type { NextApiRequest, NextApiResponse } from 'next';

export default function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  // req.body는 any 타입입니다.
  const { name } = req.body; 
  res.status(200).json({ message: `Hello ${name}` });
}
```

여기서 `req.body`는 기본적으로 `any` 타입입니다. TypeScript를 쓰는 의미가 퇴색되죠. **Zod**나 **Class Validator** 같은 라이브러리를 써서 검증할 수도 있지만, 간단한 API에는 과도한 설정이 될 수 있습니다. 

가장 깔끔한 해결책은 **제네릭(Generic)을 활용해 Request와 Response의 타입을 명확히 명시하는 것**입니다.

## 3. 해결책: 제네릭 타입 적용하기

### 3.1. 사용자 정의 타입 정의

먼저, API의 입출력 타입을 정의합니다.

```typescript
// types/user.ts
export interface UserRequestBody {
  userId: string;
  action: 'subscribe' | 'unsubscribe';
}

export interface UserResponseSuccess {
  success: true;
  message: string;
}

export interface UserResponseError {
  success: false;
  error: string;
}

export type UserResponse = UserResponseSuccess | UserResponseError;
```

### 3.2. 타입이 보장된 핸들러 함수 만들기

이제 이 타입을 API 핸들러에 적용해보겠습니다. `NextApiRequest`의 `body` 타입을 오버라이딩하는 것이 핵심입니다.

```typescript
// pages/api/users.ts
import type { NextApiRequest, NextApiResponse } from 'next';
import type { UserRequestBody, UserResponse } from '@/types/user';

// 1. NextApiRequest를 확장하여 body 타입을 좁힙니다.
typed NextApiRequestWithBody = NextApiRequest & {
  body: UserRequestBody;
};

// 2. 핸들러 함수에 제네릭을 적용합니다.
export default async function handler(
  req: NextApiRequestWithBody,
  res: NextApiResponse<UserResponse>
) {
  // 요청 메서드 검증
  if (req.method !== 'POST') {
    return res.status(405).json({ 
      success: false, 
      error: 'Method not allowed' 
    });
  }

  try {
    // 3. req.body가 이제 타입 안전하게 보장됩니다!
    const { userId, action } = req.body;

    // 비즈니스 로직 예시 (DB 호출 등)
    if (action === 'subscribe') {
      // ... 구독 로직 ...
      console.log(`User ${userId} subscribed.`);
    } else {
      console.log(`User ${userId} unsubscribed.`);
    }

    // 4. 응답도 타입 체크를 받습니다.
    return res.status(200).json({ 
      success: true, 
      message: 'Action completed successfully' 
    });

  } catch (error) {
    console.error(error);
    return res.status(500).json({ 
      success: false, 
      error: 'Internal Server Error' 
    });
  }
}
```

## 4. 클라이언트 사이드와의 연동

서버에서 타입을 정의했다면, 클라이언트에서도 해당 타입을 재사용하여 일관성을 유지해야 합니다. 이를 **tRPC** 없이 순수 TypeScript 환경에서 구현하는 방법입니다.

```typescript
// lib/api.ts
import type { UserRequestBody, UserResponse } from '@/types/user';

const API_ENDPOINT = '/api/users';

export const updateUserAction = async (data: UserRequestBody): Promise<UserResponse> => {
  const response = await fetch(API_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    // 에러 처리 로직
    throw new Error('API request failed');
  }

  return response.json();
};
```

이제 컴포넌트에서 다음과 같이 사용할 수 있습니다.

```typescript
// components/SubscriptionButton.tsx
import { updateUserAction } from '@/lib/api';

const handleClick = async () => {
  const result = await updateUserAction({ 
    userId: 'user-123', 
    action: 'subscribe' 
  });
  
  if (result.success) {
    alert(result.message); // 타입 추론됨
  }
};
```

## 5. 결론 및 팁

Next.js API Routes는 별도의 서버를 구축하지 않고도 풀스택 애플리케이션을 구현할 수 있는 강력한 도구입니다. 다만, JavaScript의 유연함 때문에 타입 안전성이 희생될 수 있는데, 위에서 소개한 **제네릭 타입 확장 패턴**을 사용하면 복잡한 외부 라이브러리 도입 없이도 안전한 코드를 작성할 수 있습니다.

**요약:**
1. 요청/응답 데이터의 인터페이스를 별도로 정의하세요.
2. `NextApiRequest & { body: MyType }` 패턴을 사용해 요청 본문의 타입을 강제하세요.
3. `NextApiResponse<MyType>`으로 응답 구조를 보장하세요.
4. 클라이언트와 서버에서 동일한 타입을 공유하여 중복을 줄이세요.

이 방식은 앞서 언급한 **MCP(Model Context Protocol)** 도구를 구현하거나, **AI 댓글 시스템**과 같은 내부 API를 구축할 때도 매우 유용하게 사용됩니다. 코드의 신뢰성을 높이고, 런타임 에러를 줄이는 가장 현실적인 접근법입니다.
