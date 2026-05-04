+++
title = "The Ultimate Guide to Next.js API Routes: Building Type-Safe Servers with TypeScript"
date = "2026-05-03T12:48:53+09:00"
draft = "false"
tags = ["Next.js", "TypeScript", "API", "Node.js", "Web Development"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

# The Ultimate Guide to Next.js API Routes: Building Type-Safe Servers with TypeScript

Recently, Mercury's Haskell-based backend story became a hot topic on **Hacker News**. While robust systems that handle massive traffic are important, for ordinary web developers like us, **fast development speed and maintainability** are essential. Especially in startups or personal projects, it is difficult to give up the convenience of frameworks.

In this post, we will cover how to build efficient server-side logic while ensuring type safety using **Next.js API Routes**. This method maximizes the benefits of a Monorepo style where the API and frontend are managed in a single repository, similar to the backend of the 'AI Auto-Comment System' or 'MCP Server' we built earlier.

## 1. API Routes vs Route Handlers (App Router)

The first dilemma when using Next.js is whether to use `pages/api` from the Pages Router or `route.ts` from the App Router.

- **Pages Router (`pages/api`):** Relies on the Node.js server environment, and middleware settings are intuitive. It is great for using existing Node.js ecosystem middleware as is.
- **App Router (`app/api`):** Supports Edge Runtime for faster startup times and global distributed deployment, but there may be constraints on using Node.js-specific features (e.g., direct file system access).

In this guide, we will use the currently most stable and intuitive **Pages Router-based API Routes** as examples, but the typing method can be applied equally to the App Router.

## 2. The Problem: Loose Request/Response Types

The default type definition for a Next.js API handler is as follows.

```typescript
import type { NextApiRequest, NextApiResponse } from 'next';

export default function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  // req.body is of type any.
  const { name } = req.body; 
  res.status(200).json({ message: `Hello ${name}` });
}
```

Here, `req.body` is basically of type `any`. The significance of using TypeScript fades. You can use libraries like **Zod** or **Class Validator** for validation, but this can be excessive setup for simple APIs.

The cleanest solution is to **explicitly specify the types for Request and Response by utilizing Generics**.

## 3. Solution: Applying Generic Types

### 3.1. Defining Custom Types

First, define the input and output types for the API.

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

### 3.2. Creating a Type-Safe Handler Function

Now, let's apply this type to the API handler. The key is overriding the `body` type of `NextApiRequest`.

```typescript
// pages/api/users.ts
import type { NextApiRequest, NextApiResponse } from 'next';
import type { UserRequestBody, UserResponse } from '@/types/user';

// 1. Extend NextApiRequest to narrow down the body type.
type NextApiRequestWithBody = NextApiRequest & {
  body: UserRequestBody;
};

// 2. Apply generics to the handler function.
export default async function handler(
  req: NextApiRequestWithBody,
  res: NextApiResponse<UserResponse>
) {
  // Validate request method
  if (req.method !== 'POST') {
    return res.status(405).json({ 
      success: false, 
      error: 'Method not allowed' 
    });
  }

  try {
    // 3. req.body is now guaranteed to be type-safe!
    const { userId, action } = req.body;

    // Example business logic (DB calls, etc.)
    if (action === 'subscribe') {
      // ... subscription logic ...
      console.log(`User ${userId} subscribed.`);
    } else {
      console.log(`User ${userId} unsubscribed.`);
    }

    // 4. The response also receives type checking.
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

## 4. Integration with Client Side

If you define types on the server, you should reuse those types on the client to maintain consistency. Here is how to implement this in a pure TypeScript environment without **tRPC**.

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
    // Error handling logic
    throw new Error('API request failed');
  }

  return response.json();
};
```

Now you can use it in a component as follows.

```typescript
// components/SubscriptionButton.tsx
import { updateUserAction } from '@/lib/api';

const handleClick = async () => {
  const result = await updateUserAction({ 
    userId: 'user-123', 
    action: 'subscribe' 
  });
  
  if (result.success) {
    alert(result.message); // Type inferred
  }
};
```

## 5. Conclusion and Tips

Next.js API Routes is a powerful tool that allows you to implement full-stack applications without building a separate server. However, type safety can be sacrificed due to the flexibility of JavaScript. By using the **Generic Type Extension Pattern** introduced above, you can write safe code without introducing complex external libraries.

**Summary:**
1. Define interfaces for request/response data separately.
2. Use the `NextApiRequest & { body: MyType }` pattern to enforce the type of the request body.
3. Guarantee the response structure with `NextApiResponse<MyType>`.
4. Share the same types between client and server to reduce duplication.

This approach is also very useful when implementing the aforementioned **MCP (Model Context Protocol)** tools or building internal APIs like the **AI Comment System**. It is the most realistic approach to increasing code reliability and reducing runtime errors.