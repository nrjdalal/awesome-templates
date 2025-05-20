"use client"

import { useState } from "react"

import { zodResolver } from "@hookform/resolvers/zod"
import { RiGithubFill, RiGoogleFill } from "@remixicon/react"
import { GalleryVerticalEnd, Loader2 } from "lucide-react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import * as z from "zod"

import { signIn } from "@/lib/auth/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"

const formSchema = z.object({
  email: z.string().min(2, {
    message: "Please enter a valid email address!",
  }),
})

export default function Component() {
  const [loader, setLoader] = useState<"email" | "github" | "google" | null>(null)

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: "",
    },
  })

  const onSubmit = async (data: z.infer<typeof formSchema>) => {
    setLoader("email")
    const res = await signIn.magicLink({
      email: data.email,
      callbackURL: "/x",
    })
    if (res.error) {
      toast.error(res.error.message)
      setLoader(null)
    } else {
      toast.success("Check your email for the magic link!")
      setLoader(null)
    }
    form.reset()
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button className="w-24 cursor-pointer" size="sm" variant="outline">
          Login
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md sm:max-w-md">
        <DialogHeader className="sr-only">
          <DialogTitle className="text-center">Sign in/up</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-6">
          <div className="flex flex-col items-center gap-2">
            <div className="flex flex-col items-center gap-2 font-medium">
              <div className="flex size-8 items-center justify-center rounded-md">
                <GalleryVerticalEnd className="size-6" />
              </div>
              <span className="sr-only">ACME Inc.</span>
            </div>
            <h1 className="text-xl font-semibold">Welcome to ACME Inc.</h1>
          </div>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem className="flex flex-col items-center gap-y-3">
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        className="text-center focus:placeholder:opacity-0"
                        placeholder="admin@nrjdalal.com"
                        {...field}
                        disabled={loader === "email"}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button
                type="submit"
                variant="secondary"
                className="w-full cursor-pointer"
                disabled={loader === "email"}
              >
                {loader === "email" ? <Loader2 className="size-5 animate-spin" /> : null}
                Sign in/up
              </Button>
            </form>
          </Form>
          <div className="after:border-border relative text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:flex after:items-center after:border-t">
            <span className="bg-background text-muted-foreground relative z-10 px-2 text-xs">
              OR
            </span>
          </div>
          <div className="grid gap-4">
            <Button
              variant="outline"
              type="button"
              className="w-full cursor-pointer"
              onClick={async () => {
                setLoader("github")
                const res = await signIn.social({
                  provider: "github",
                  callbackURL: "/x",
                })
                if (res.error) {
                  toast.error(res.error.message)
                  setLoader(null)
                }
              }}
              disabled={loader === "github"}
            >
              {loader === "github" ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <RiGithubFill className="size-5" />
              )}
              Continue with Github
            </Button>
            <Button
              variant="outline"
              type="button"
              className="w-full cursor-pointer"
              onClick={async () => {
                setLoader("google")
                const res = await signIn.social({
                  provider: "google",
                  callbackURL: "/x",
                })
                if (res.error) {
                  toast.error(res.error.message)
                  setLoader(null)
                }
              }}
              disabled={loader === "google"}
            >
              {loader === "google" ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <RiGoogleFill className="size-5" />
              )}
              Continue with Google
            </Button>
            <div className="text-muted-foreground *:[a]:hover:text-primary text-center text-xs text-balance *:[a]:underline *:[a]:underline-offset-4">
              By clicking continue, you agree to our <a href="#">Terms of Service</a> and{" "}
              <a href="#">Privacy Policy</a>.
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
