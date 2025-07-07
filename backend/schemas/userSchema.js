import { z } from "zod";

const createUserSchema = z.object({
  id:z.string(),
  email: z.string().email(),
  name: z.string().min(1).optional()
});

const updateUserSchema = z.object({
  name: z.string().min(1).optional()
});

export {
  createUserSchema,
  updateUserSchema
};
